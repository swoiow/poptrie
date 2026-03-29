# poptrie

High-performance IP lookup backed by Rust. This public repository owns the final Python facade and publishes wheels.

Stable public contract:
- `from poptrie import IpSearcher`
- `IpSearcher` resolves to `poptrie.ip_searcher.IpSearcher`
- native extension details are intentionally hidden behind the facade

## Installation

Install from PyPI:

```bash
pip install poptrie
```

## Usage

```python
import socket
from pathlib import Path

from poptrie import IpSearcher


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

## Tests

Public facade verification:

```bash
PYTHONPATH=<private-src> python -m unittest discover tests
```

## Notes

- Country codes are returned as u16 in Rust and converted to 2-letter strings in Python.
- `*_fast` methods are for high-throughput packed inputs (stride 4/16).
- Wheel repack injects the public `__init__.py` and `ip_searcher.py` into the final package.
