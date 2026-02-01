import argparse
import ipaddress
import urllib.request
from pathlib import Path

from build_bin import BinBuilder


def _load_cidrs(url: str) -> list[str]:
    with urllib.request.urlopen(url) as response:
        content = response.read().decode("utf-8")
    cidrs = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cidrs.append(line)
    return cidrs


def _validate_first(cidr_list: list[str]) -> None:
    if not cidr_list:
        raise SystemExit("No CIDR data found")
    ipaddress.ip_network(cidr_list[0], strict=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build poptrie CN bin from CIDR list")
    parser.add_argument("--url", required=True, help="CIDR list URL")
    parser.add_argument("--output", required=True, help="Output bin path")
    args = parser.parse_args()

    cidrs = _load_cidrs(args.url)
    _validate_first(cidrs)

    builder = BinBuilder()
    for cidr in cidrs:
        builder.add_cidr(cidr)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    builder.save(str(output_path))


if __name__ == "__main__":
    main()
