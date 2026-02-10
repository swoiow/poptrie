# poptrie

基于 Rust 的高性能 IP 查询库，通过 PyO3 暴露给 Python。

## 环境要求

- Python 3.8+

## Python 使用示例（V2）

```python
import socket
from pathlib import Path

from ip_searcher import IpSearcher


bin_path = Path("china-ip.bin")
searcher = IpSearcher(bin_path)

ip_bytes = socket.inet_pton(socket.AF_INET, "1.0.1.1")
print(searcher.contains_ip("1.0.1.1"))
print(searcher.lookup_country("1.0.1.1"))
print(searcher.is_cn("1.0.1.1"))

ips = ["1.0.1.1", "8.8.8.8", "240e::1", "2001:db8::"]
print(searcher.contains_ips(ips))
print(searcher.lookup_countries(ips))  # ("ip", "CN" 或 None)
print(searcher.is_cn_batch(ips))

v4_ips = ["1.0.1.1", "8.8.8.8", "110.16.0.1", "127.0.0.1"]
packed_v4 = b"".join(socket.inet_pton(socket.AF_INET, ip) for ip in v4_ips)
print(searcher.contains_ips_fast(packed_v4, is_v6=False))
print(searcher.lookup_countries_fast(packed_v4, is_v6=False))
print(searcher.is_cn_fast(packed_v4, is_v6=False))
```

## API 说明

- 国家码在 Rust 中以 u16 返回，Python 层负责转为 2 位字符串。
- `*_fast` 适合高吞吐场景，使用 4/16 字节步长扁平化字节流。

## 测试

```bash
python -m unittest discover tests
```

## 示例

运行内置示例：

```bash
python example.py
python ip_searcher.py
```
