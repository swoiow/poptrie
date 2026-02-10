# Poptrie BIN 布局与构建流程

本文描述如何从 TXT 目录生成二进制文件。

## 输入与编码

- TXT 目录中每个文件名就是国家码，例如 `CN.txt`。
- 国家码编码为 u16：
  - `code = (ord('C') << 8) | ord('N')`
- 每条 CIDR 会插入 Trie，并带上对应的国家码 value。

## Trie 构建

- Trie 按字节路径构建（IPv4/IPv6 都是字节序列）。
- 插入 CIDR：
  - 按掩码长度走路径。
  - 目标位置标记为叶子并写入 value。
  - 如果上层已有更大前缀叶子，则忽略更小 CIDR。

## 剪枝

- 当一个节点的 256 个子节点全部是叶子，且 value 相同，
  就把该节点合并为叶子并删除子树。

## Node 序列化（BFS）

每个 Node 固定 72 字节：

```
[ Child_BM 32 ][ Leaf_BM 32 ][ Child_Offset u32 ][ Leaf_Base_Index u32 ]
```

- `Child_BM`：该节点哪些分支有子树。
- `Leaf_BM`：该节点哪些分支是叶子。
- `Child_Offset`：子节点在文件中的起始偏移（字节）。
- `Leaf_Base_Index`：该节点第一个叶子在 Value 数组里的起始下标。

BFS 过程中：

- 叶子按键顺序收集，value 按顺序追加到 Value 数组。
- `Leaf_Base_Index = len(ValueArray)`（追加前的长度）。

## Value 数组

- Node 区写完后，紧接着追加一个连续的 u16 数组。
- 顺序与 BFS 收集叶子的顺序一致。

## 查找逻辑

- 若 `leaf_bitmap` 第 k 位为 1：
  - `m = popcount(leaf_bitmap[0..k))`
  - `index = base_index + m`
  - `value = values[index]`（u16 国家码）
