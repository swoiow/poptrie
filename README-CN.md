# poptrie

基于 Rust 的高性能 IP 查询库。公共仓只发布 wheel，不提供构建工具。

## 使用示例

```python
import socket
from pathlib import Path

from poptrie.ip_searcher import IpSearcher


bin_path = Path("china-ip.bin")
searcher = IpSearcher(bin_path)

print("1.0.1.1" in searcher)
print(searcher.lookup("1.0.1.1"))
print(searcher.get_country("1.0.1.1"))
print(searcher.is_china("1.0.1.1"))

ips = ["1.0.1.1", "8.8.8.8", "240e::1", "2001:db8::"]
print(searcher.batch_lookup(ips))
print(searcher.batch_get_countries(ips))

v4_ips = ["1.0.1.1", "8.8.8.8", "110.16.0.1", "127.0.0.1"]
packed_v4 = b"".join(socket.inet_pton(socket.AF_INET, ip) for ip in v4_ips)
print(searcher.lookup_fast(packed_v4, is_v6=False))
print(searcher.get_countries_fast(packed_v4, is_v6=False))
```

## 示例

```bash
python example.py
```

## 说明

- Rust 返回 u16 国家码，Python 负责转换为 2 位字符串。
- `*_fast` 适合高吞吐场景，使用 4/16 字节步长扁平化字节流。
