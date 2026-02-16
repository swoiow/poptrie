import argparse
import ipaddress
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from build_bin import BinBuilder, load_txt_dirs


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


def _download_zip(url: str, dest: Path) -> Path:
    with urllib.request.urlopen(url) as response:
        data = response.read()
    zip_path = dest / "archive.zip"
    zip_path.write_bytes(data)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest)
    return dest


def _find_dir(root: Path, suffix: str) -> Path:
    for path in root.rglob("*"):
        if path.is_dir() and path.as_posix().endswith(suffix):
            return path
    raise SystemExit(f"Directory not found: {suffix}")


def _validate_first(cidr_list: list[str]) -> None:
    if not cidr_list:
        raise SystemExit("No CIDR data found")
    ipaddress.ip_network(cidr_list[0], strict=False)


def _build_cn(output_path: Path, url: str) -> None:
    cidrs = _load_cidrs(url)
    _validate_first(cidrs)
    builder = BinBuilder()
    cn_code = (ord("C") << 8) | ord("N")
    for cidr in cidrs:
        builder.add_cidr(cidr, cn_code)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    builder.save(str(output_path))


def _build_geoip_text(output_path: Path, zip_url: str) -> None:
    temp_dir = Path(tempfile.mkdtemp())
    try:
        _download_zip(zip_url, temp_dir)
        text_dir = _find_dir(temp_dir, "text")
        builder = BinBuilder()
        load_txt_dirs(builder, [text_dir])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        builder.save(str(output_path))
    finally:
        shutil.rmtree(temp_dir)


def _build_iana(output_path: Path, zip_url: str) -> None:
    """ TODO: 需要精细化的 IANA 数据时，使用 https://github.com/harmonsir/iana-geoip """
    temp_dir = Path(tempfile.mkdtemp())
    try:
        _download_zip(zip_url, temp_dir)
        ipv4_dir = _find_dir(temp_dir, "TXT/IPV4")
        ipv6_dir = _find_dir(temp_dir, "TXT/IPV6")
        builder = BinBuilder()
        load_txt_dirs(builder, [ipv4_dir, ipv6_dir])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        builder.save(str(output_path))
    finally:
        shutil.rmtree(temp_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build poptrie geo bins")
    parser.add_argument("--cn-url", required=True, help="CN CIDR list URL")
    parser.add_argument("--geoip-zip-url", required=True, help="GeoIP text zip URL")
    parser.add_argument("--iana-zip-url", required=True, help="IANA zip URL")
    parser.add_argument("--out-cn", required=True, help="Output geo-cn.dat path")
    parser.add_argument("--out-geoip", required=True, help="Output bgp-geoip.dat path")
    parser.add_argument("--out-iana", required=True, help="Output iana-geoip.dat path")
    args = parser.parse_args()

    _build_cn(Path(args.out_cn), args.cn_url)
    _build_geoip_text(Path(args.out_geoip), args.geoip_zip_url)
    _build_iana(Path(args.out_iana), args.iana_zip_url)


if __name__ == "__main__":
    main()
