# poptrie

基于 Rust 的高性能 IP 查询库。这个公共仓负责最终 Python facade 与 wheel 发布。

稳定公开约定：
- `from poptrie import IpSearcher`
- `IpSearcher` 固定指向 `poptrie.ip_searcher.IpSearcher`
- native 扩展细节由 facade 封装，不再作为顶层公开语义

## 安装

通过 PyPI 安装：

```bash
pip install poptrie
```

## 使用示例

```python
import socket
from pathlib import Path

from poptrie import IpSearcher


bin_path = Path("china-ip.bin")
searcher = IpSearcher(bin_path)

print("1.0.1.1" in searcher)
print(searcher.contains_ip("1.0.1.1"))
print(searcher.lookup_country("1.0.1.1"))
print(searcher.is_china("1.0.1.1"))

ips = ["1.0.1.1", "8.8.8.8", "240e::1", "2001:db8::"]
print(searcher.contains_ips(ips))
print(searcher.lookup_countries(ips))
print(searcher.matches_countries(ips, "CN"))

v4_ips = ["1.0.1.1", "8.8.8.8", "110.16.0.1", "127.0.0.1"]
packed_v4 = b"".join(socket.inet_pton(socket.AF_INET, ip) for ip in v4_ips)
print(searcher.contains_packed(packed_v4, is_v6=False))
print(searcher.lookup_countries_packed(packed_v4, is_v6=False))
print(searcher.matches_country_packed(packed_v4, "CN", is_v6=False))
```

## 示例

```bash
python example.py
```

## 测试

公开 facade 验证：

```bash
PYTHONPATH=<private-src> python -m unittest discover tests
```

## 说明

- Rust 返回 u16 国家码，Python 负责转换为 2 位字符串。
- `*_packed` 适合高吞吐场景，使用 4/16 字节步长扁平化字节流。
- 最终 wheel 会在 repack 时注入公共仓的 `__init__.py` 与 `ip_searcher.py`。
