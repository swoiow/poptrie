# poptrie

基于 Rust 的高性能 IP 查询库，通过 PyO3 暴露给 Python。

## 环境要求

- Python 3.8+
- Rust 工具链
- `maturin`

## 构建与安装

创建虚拟环境并以开发模式安装：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip maturin
maturin develop --release
```

构建 wheel：

```bash
maturin build --release --out dist
```

## 生成二进制数据

搜索器读取 `build_bin.py` 生成的二进制文件：

```bash
python build_bin.py
```

如果你修改了构建逻辑，需要重新生成 bin 文件（当前节点对齐为 72 字节）。

## Python 使用示例

```python
import socket
from pathlib import Path

import poptrie


bin_path = Path("china_ip.bin")
searcher = poptrie.IpSearcher(str(bin_path))

ip_bytes = socket.inet_pton(socket.AF_INET, "1.0.1.1")
print(searcher.is_china_ip(ip_bytes))

ips = ["1.0.1.1", "8.8.8.8", "240e::1", "2001:db8::"]
print(searcher.batch_check_strings(ips))

v4_ips = ["1.0.1.1", "8.8.8.8", "110.16.0.1", "127.0.0.1"]
packed_v4 = b"".join(socket.inet_pton(socket.AF_INET, ip) for ip in v4_ips)
print(searcher.batch_check_packed(packed_v4, is_v6=False))
```

## API 说明

- `is_china_ip` 接收 IPv4/IPv6 的 bytes（长度 4 或 16）。
- `batch_check_strings` 直接接收字符串列表，顺序稳定。
- `batch_check_packed` 接收扁平化字节流，按固定步长 4/16 解析。

## 测试

```bash
python -m unittest discover tests
```

## 示例

运行内置示例：

```bash
python example.py
python example_production.py
```
