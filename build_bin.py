import argparse
import socket
import struct
from pathlib import Path


class Node:
    __slots__ = ["children", "is_leaf", "value"]

    def __init__(self):
        self.children = {}  # byte -> Node
        self.is_leaf = False
        self.value = None


class BinBuilder:
    # Node layout: [Child_BM 32] [Leaf_BM 32] [Child_Offset u32] [Leaf_Base_Index u32]
    NODE_SIZE = 72
    HEADER_SIZE = 16
    MAGIC = b"PTV2"

    def __init__(self):
        self.root = Node()

    def add_cidr(self, cidr, value=1):
        """添加并自动合并子网"""
        if not (1 <= value <= 0xFFFF):
            raise ValueError("value must be in range 1..65535")

        try:
            ip_part, mask_part = cidr.split("/")
            mask = int(mask_part)
            family = socket.AF_INET6 if ":" in ip_part else socket.AF_INET
            ip_bytes = socket.inet_pton(family, ip_part)
        except Exception:
            return

        curr = self.root
        steps = mask >> 3  # mask // 8
        remaining = mask & 7  # mask % 8

        # 1. 沿路径前进，如果中途遇到更短的叶子（已覆盖），直接返回
        for i in range(steps):
            if curr.is_leaf:
                return

            byte = ip_bytes[i]
            if byte not in curr.children:
                curr.children[byte] = Node()
            curr = curr.children[byte]

        # 2. 处理末尾位
        if remaining == 0:
            curr.is_leaf = True
            curr.value = value
            curr.children = {}  # 覆盖所有更长的子路径
        else:
            if curr.is_leaf:
                return
            shift = 8 - remaining
            start_byte = ip_bytes[steps] & (0xFF << shift)
            end_byte = start_byte | (0xFF >> remaining)

            for b in range(start_byte, end_byte + 1):
                # 标记为叶子节点
                n = Node()
                n.is_leaf = True
                n.value = value
                curr.children[b] = n

    def _prune(self, node):
        """递归剪枝：如果 256 个子节点全是叶子且值一致，合并为父节点叶子"""
        if not node.children:
            return node.is_leaf

        all_children_are_leaf = (len(node.children) == 256)
        first_value = None

        # 遍历子节点进行递归剪枝
        for b in list(node.children.keys()):
            child = node.children[b]
            child_is_leaf = self._prune(child)
            if not child_is_leaf:
                all_children_are_leaf = False
            elif all_children_are_leaf:
                if first_value is None:
                    first_value = child.value
                elif child.value != first_value:
                    all_children_are_leaf = False

        if all_children_are_leaf and first_value is not None:
            node.is_leaf = True
            node.value = first_value
            node.children = {}
            return True

        return node.is_leaf

    def save(self, output_path):
        """序列化为 BFS 结构的二进制文件"""
        print("Pruning tree...")
        self._prune(self.root)

        final_data = bytearray()
        values = []
        current_layer = [self.root]
        # 初始偏移量：Header 之后就是第一层节点
        next_layer_start_offset = self.HEADER_SIZE + len(current_layer) * self.NODE_SIZE

        print("Serializing...")
        while current_layer:
            next_layer = []
            for node in current_layer:
                child_bm_int = 0
                leaf_bm_int = 0

                # 按照索引顺序处理子节点
                sorted_indices = sorted(node.children.keys())

                nodes_with_children = []
                local_leaf_values = []
                for k in sorted_indices:
                    child_node = node.children[k]
                    # 计算 bit 在 256 位中的位置 (Big-Endian)
                    bit_pos = 255 - k

                    if child_node.is_leaf:
                        leaf_bm_int |= (1 << bit_pos)
                        local_leaf_values.append(child_node.value)

                    if child_node.children:
                        child_bm_int |= (1 << bit_pos)
                        nodes_with_children.append(child_node)

                # 快速将 256 位整数转为 32 字节
                final_data.extend(child_bm_int.to_bytes(32, "big"))
                final_data.extend(leaf_bm_int.to_bytes(32, "big"))

                base_index = len(values)
                values.extend(local_leaf_values)

                jump_offset = 0
                if nodes_with_children:
                    jump_offset = next_layer_start_offset
                    next_layer.extend(nodes_with_children)
                    next_layer_start_offset += len(nodes_with_children) * self.NODE_SIZE

                final_data.extend(struct.pack("<II", jump_offset, base_index))

            current_layer = next_layer

        # 写入文件
        node_count = len(final_data) // self.NODE_SIZE
        values_count = len(values)
        header = struct.pack("<4sIII", self.MAGIC, node_count, values_count, 0)

        with open(output_path, "wb") as f:
            f.write(header)
            f.write(final_data)
            # 分块写入 values (u16)
            for i in range(0, len(values), 1000):
                chunk = values[i:i + 1000]
                f.write(struct.pack(f"<{len(chunk)}H", *chunk))

        total_size_kb = (len(header) + len(final_data) + values_count * 2) / 1024
        print(f"Build complete. Nodes: {node_count}, Values: {values_count}, Size: {total_size_kb:.2f} KB")


def country_code_to_u16(country_code):
    country_code = country_code.upper()
    return (ord(country_code[0]) << 8) | ord(country_code[1])


def load_txt_dir(builder, txt_dir):
    all_cidrs = []
    print(f"Loading files from {txt_dir}...")
    for path in Path(txt_dir).glob("*.txt"):
        country_code = path.stem.upper()
        if len(country_code) != 2:
            continue
        val = country_code_to_u16(country_code)
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    all_cidrs.append((line, val))

    # 核心优化：按掩码长度从小到大排序
    # 这样大子网会先添加，小子网在 add_cidr 中会被快速跳过
    print(f"Sorting {len(all_cidrs)} CIDRs by mask length...")
    all_cidrs.sort(key=lambda x: int(x[0].split("/")[1]))

    print("Building tree...")
    for cidr, val in all_cidrs:
        builder.add_cidr(cidr, val)


def load_txt_dirs(builder, txt_dirs):
    for txt_dir in txt_dirs:
        load_txt_dir(builder, txt_dir)


def main():
    parser = argparse.ArgumentParser(description="Build poptrie binary from TXT directory.")
    parser.add_argument("--input", help="Input TXT directory", default=None)
    parser.add_argument("--output", help="Output bin file path", default="./geoip.bin")
    args = parser.parse_args()

    builder = BinBuilder()

    input_dir = args.input
    if input_dir and Path(input_dir).exists():
        load_txt_dir(builder, input_dir)
        builder.save(args.output)
    else:
        print("Error: No valid input directory found.")


if __name__ == "__main__":
    main()
