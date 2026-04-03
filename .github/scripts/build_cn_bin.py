import argparse
import os
import shutil
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


def _build_cn(output_path: Path, url: str, private_src: Path) -> None:
    temp_dir = Path(tempfile.mkdtemp())
    try:
        cidrs = _load_cidrs(url)
        if not cidrs:
            raise SystemExit("No CIDR data found")
        input_dir = temp_dir / "text"
        input_dir.mkdir(parents=True, exist_ok=True)
        (input_dir / "CN.txt").write_text("\n".join(cidrs) + "\n", encoding="utf-8")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _run_build_geoip(
            private_src,
            "--input-dir",
            str(input_dir),
            "--output-dat",
            str(output_path),
        )
    finally:
        shutil.rmtree(temp_dir)


def _build_geoip_text(output_path: Path, zip_url: str, private_src: Path) -> None:
    temp_dir = Path(tempfile.mkdtemp())
    try:
        _download_zip(zip_url, temp_dir)
        text_dir = _find_dir(temp_dir, "text")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _run_build_geoip(
            private_src,
            "--input-dir",
            str(text_dir),
            "--output-dat",
            str(output_path),
        )
    finally:
        shutil.rmtree(temp_dir)


def _build_iana(output_path: Path, zip_url: str, private_src: Path) -> None:
    temp_dir = Path(tempfile.mkdtemp())
    try:
        _download_zip(zip_url, temp_dir)
        ipv4_dir = _find_dir(temp_dir, "TXT/IPV4")
        ipv6_dir = _find_dir(temp_dir, "TXT/IPV6")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _run_build_geoip(
            private_src,
            "--ipv4-dir",
            str(ipv4_dir),
            "--ipv6-dir",
            str(ipv6_dir),
            "--output-dat",
            str(output_path),
        )
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
    private_src = _resolve_private_src()

    _build_cn(Path(args.out_cn), args.cn_url, private_src)
    _build_geoip_text(Path(args.out_geoip), args.geoip_zip_url, private_src)
    _build_iana(Path(args.out_iana), args.iana_zip_url, private_src)


if __name__ == "__main__":
    main()
