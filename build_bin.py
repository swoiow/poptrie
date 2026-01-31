import socket
import struct


class BinBuilder:
    NODE_SIZE = 68  # 32字节Child_BM + 32字节Leaf_BM + 4字节Base_Offset

    def __init__(self):
        # 根节点：{ 'children': {byte: node_dict}, 'is_leaf': bool }
        self.root = {'children': {}, 'is_leaf': False}

    def add_cidr(self, cidr):
        """添加并自动合并子网"""
        ip_part, mask_part = cidr.split('/')
        mask = int(mask_part)
        family = socket.AF_INET6 if ':' in ip_part else socket.AF_INET
        ip_bytes = socket.inet_pton(family, ip_part)

        curr = self.root
        steps = mask // 8
        remaining = mask % 8

        # 1. 沿路径向下寻址
        for i in range(steps):
            # 如果路径中已经存在叶子节点，说明当前 CIDR 已被更大网段覆盖，直接返回
            if curr['is_leaf']:
                return

            byte = ip_bytes[i]
            if byte not in curr['children']:
                curr['children'][byte] = {'children': {}, 'is_leaf': False}
            curr = curr['children'][byte]

        # 2. 处理剩余位或结束位
        if remaining == 0:
            # 正好整除，标记为叶子，并清理其下的所有子节点（因为大网覆盖小网）
            curr['is_leaf'] = True
            curr['children'] = {}
        else:
            # 处理非对齐掩码，如 /18 在第 3 字节有 2 位
            shift = 8 - remaining
            start_byte = ip_bytes[steps] & (0xFF << shift)
            end_byte = start_byte | (0xFF >> remaining)

            for b in range(start_byte, end_byte + 1):
                # 如果这个范围内的某个字节已经存在，递归处理它
                if b not in curr['children']:
                    curr['children'][b] = {'children': {}, 'is_leaf': True}
                else:
                    # 如果已存在，将其标记为叶子，并剪枝其子树
                    curr['children'][b]['is_leaf'] = True
                    curr['children'][b]['children'] = {}

    def _prune(self, node):
        """递归剪枝：如果 256 个子节点全是叶子，合并为父节点叶子"""
        if not node['children']:
            return node['is_leaf']

        # 先递归剪枝子节点
        all_children_are_leaf = len(node['children']) == 256
        for b in list(node['children'].keys()):
            child_is_leaf = self._prune(node['children'][b])
            if not child_is_leaf:
                all_children_are_leaf = False

        # 如果 256 个子节点全满且都是叶子，则向上合并
        if all_children_are_leaf:
            node['is_leaf'] = True
            node['children'] = {}
            return True

        return node['is_leaf']

    def save(self, output_path):
        """执行剪枝并序列化为 BFS 结构的二进制文件"""
        # 1. 先进行全局剪枝优化压缩率
        self._prune(self.root)

        final_data = bytearray()
        current_layer = [self.root]
        # 下一层节点在文件中的起始偏移（根节点之后）
        next_layer_start_offset = self.NODE_SIZE

        while current_layer:
            next_layer = []
            for node in current_layer:
                child_bm = bytearray(32)
                leaf_bm = bytearray(32)

                # 获取 0-255 的排序键
                sorted_keys = sorted(node['children'].keys())

                # 收集本节点中有子树的节点，它们将排在 next_layer
                nodes_with_children = []

                for k in sorted_keys:
                    child_node = node['children'][k]

                    # 标记 Leaf Bitmap: 只要这个字节是终点
                    if child_node['is_leaf']:
                        leaf_bm[k >> 3] |= (1 << (7 - (k % 8)))

                    # 标记 Child Bitmap: 只有还有子树的才标记，用于跳转
                    if child_node['children']:
                        child_bm[k >> 3] |= (1 << (7 - (k % 8)))
                        nodes_with_children.append(child_node)

                # 写入节点数据
                final_data.extend(child_bm)
                final_data.extend(leaf_bm)

                if nodes_with_children:
                    # 记录跳转到下一层这些子节点的起始偏移
                    final_data.extend(struct.pack("<I", next_layer_start_offset))
                    next_layer.extend(nodes_with_children)
                    next_layer_start_offset += len(nodes_with_children) * self.NODE_SIZE
                else:
                    # 没有子节点可跳转
                    final_data.extend(struct.pack("<I", 0))

            current_layer = next_layer

        with open(output_path, "wb") as f:
            f.write(final_data)
        print(f"构建完成！压缩后大小: {len(final_data) / 1024:.2f} KB")


# --- 使用方式 ---
builder = BinBuilder()
# 这里放入你收集的中国 IP CIDR 列表
china_cidrs = ["1.0.1.0/24", "110.16.0.0/12", "240e::/18"]
for c in china_cidrs:
    builder.add_cidr(c)

builder.save("china_ip.bin")
