# poptrie

High-performance IP lookup backed by Rust. This public repo only ships wheels; it does not include build tooling.

## Usage

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

## Example

```bash
python example.py
```

## Notes

- Country codes are returned as u16 in Rust and converted to 2-letter strings in Python.
- `*_fast` methods are for high-throughput packed inputs (stride 4/16).
