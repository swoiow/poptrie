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

## Example

```bash
python example.py
```

## Tests

Public facade verification:

```bash
python -m unittest discover tests
```

## Notes

- Country lookups are resolved in Rust and exposed as 2-letter strings in Python.
- `*_packed` methods are intended for high-throughput byte-oriented workloads.
- The public Python facade lives in `poptrie/__init__.py` and `poptrie/ip_searcher.py`.
- Files such as `*-overlap.csv` are input conflict audit reports, not evidence that the final `.dat` files still contain overlapping CIDRs.
