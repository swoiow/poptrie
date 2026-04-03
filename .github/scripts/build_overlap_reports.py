import argparse
import os
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path


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


def _resolve_private_src() -> Path:
    private_src = os.environ.get("POPTRIE_PRIVATE_SRC")
    if not private_src:
        raise SystemExit("POPTRIE_PRIVATE_SRC is required")
    return Path(private_src).resolve()


def _run_build_geoip(private_src: Path, *args: str) -> None:
    subprocess.run(
        ["cargo", "run", "--release", "--bin", "build_geoip", "--", *args],
        cwd=private_src,
        check=True,
    )


def _build_cn_overlap(output_dat: Path, output_csv: Path, url: str, private_src: Path) -> None:
    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        input_dir = temp_dir / "text"
        input_dir.mkdir(parents=True, exist_ok=True)
        cidrs = _load_cidrs(url)
        if not cidrs:
            raise SystemExit("No CIDR data found")
        (input_dir / "CN.txt").write_text("\n".join(cidrs) + "\n", encoding="utf-8")
        _run_build_geoip(
            private_src,
            "--input-dir",
            str(input_dir),
            "--output-dat",
            str(output_dat),
            "--overlap-report",
            str(output_csv),
        )


def _build_geoip_overlap(output_dat: Path, output_csv: Path, zip_url: str, private_src: Path) -> None:
    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        _download_zip(zip_url, temp_dir)
        text_dir = _find_dir(temp_dir, "text")
        _run_build_geoip(
            private_src,
            "--input-dir",
            str(text_dir),
            "--output-dat",
            str(output_dat),
            "--overlap-report",
            str(output_csv),
        )


def _build_iana_overlap(output_dat: Path, output_csv: Path, zip_url: str, private_src: Path) -> None:
    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        _download_zip(zip_url, temp_dir)
        ipv4_dir = _find_dir(temp_dir, "TXT/IPV4")
        ipv6_dir = _find_dir(temp_dir, "TXT/IPV6")
        _run_build_geoip(
            private_src,
            "--ipv4-dir",
            str(ipv4_dir),
            "--ipv6-dir",
            str(ipv6_dir),
            "--output-dat",
            str(output_dat),
            "--overlap-report",
            str(output_csv),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build poptrie overlap csv reports")
    parser.add_argument("--cn-url", required=True, help="CN CIDR list URL")
    parser.add_argument("--geoip-zip-url", required=True, help="GeoIP text zip URL")
    parser.add_argument("--iana-zip-url", required=True, help="IANA zip URL")
    parser.add_argument("--out-cn-dat", required=True, help="Output geo-cn.dat path")
    parser.add_argument("--out-cn-overlap", required=True, help="Output geo-cn overlap csv path")
    parser.add_argument("--out-geoip-dat", required=True, help="Output bgp-geoip.dat path")
    parser.add_argument("--out-geoip-overlap", required=True, help="Output bgp-geoip overlap csv path")
    parser.add_argument("--out-iana-dat", required=True, help="Output iana-geoip.dat path")
    parser.add_argument("--out-iana-overlap", required=True, help="Output iana overlap csv path")
    args = parser.parse_args()

    private_src = _resolve_private_src()
    _build_cn_overlap(
        Path(args.out_cn_dat),
        Path(args.out_cn_overlap),
        args.cn_url,
        private_src,
    )
    _build_geoip_overlap(
        Path(args.out_geoip_dat),
        Path(args.out_geoip_overlap),
        args.geoip_zip_url,
        private_src,
    )
    _build_iana_overlap(
        Path(args.out_iana_dat),
        Path(args.out_iana_overlap),
        args.iana_zip_url,
        private_src,
    )


if __name__ == "__main__":
    main()
