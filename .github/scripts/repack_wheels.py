import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PACKAGE_NAME = "poptrie"
SUMMARY = "High-performance IP and country lookup backed by Rust poptrie"
AUTHOR = "HarmonSir"
AUTHOR_EMAIL = "git@pylab.me"
LICENSE = "Apache-2.0"
URL = "https://github.com/swoiow/poptrie"
PROJECT_URLS = {
    "Source": "https://github.com/swoiow/poptrie",
    "Issues": "https://github.com/swoiow/poptrie/issues",
    "Releases": "https://github.com/swoiow/poptrie/releases",
}
CLASSIFIERS = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: Apache Software License",
    "Operating System :: MacOS",
    "Operating System :: Microsoft :: Windows",
    "Operating System :: POSIX :: Linux",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3 :: Only",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    "Programming Language :: Rust",
    "Topic :: Internet",
    "Topic :: Software Development :: Libraries :: Python Modules",
    "Typing :: Typed",
]


def _read_version(cargo_toml: Path) -> str:
    for line in cargo_toml.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("version"):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("Version not found in Cargo.toml")


def _render_metadata(version: str, readme_text: str) -> str:
    header_lines = [
        "Metadata-Version: 2.1",
        f"Name: {PACKAGE_NAME}",
        f"Version: {version}",
        f"Summary: {SUMMARY}",
        f"Home-page: {URL}",
        f"Author: {AUTHOR}",
        f"Author-email: {AUTHOR_EMAIL}",
        f"License: {LICENSE}",
        "Requires-Python: >=3.8",
        "Description-Content-Type: text/markdown",
    ]
    header_lines.extend(f"Project-URL: {label}, {url}" for label, url in PROJECT_URLS.items())
    header_lines.extend(f"Classifier: {classifier}" for classifier in CLASSIFIERS)
    return "\n".join(header_lines) + "\n\n" + readme_text.rstrip() + "\n"


def main() -> None:
    repo_root = Path(os.environ.get("GITHUB_WORKSPACE", Path.cwd())).resolve()
    private_root = Path(os.environ["POPTRIE_PRIVATE_SRC"]).resolve()
    dist_dir = repo_root / os.environ.get("POPTRIE_DIST_DIR", "dist")
    cargo_toml = private_root / "Cargo.toml"
    package_src = repo_root / "poptrie"
    readme_src = repo_root / "README.md"
    license_src = repo_root / "LICENSE"

    if not cargo_toml.exists():
        raise SystemExit("Cargo.toml not found")
    if not package_src.exists():
        raise SystemExit("poptrie package directory not found")
    if not readme_src.exists():
        raise SystemExit("README.md not found")
    if not license_src.exists():
        raise SystemExit("LICENSE not found")

    public_version = _read_version(cargo_toml)
    readme_text = readme_src.read_text(encoding="utf-8")

    wheels = sorted(dist_dir.glob("*.whl"))
    if not wheels:
        raise SystemExit("No wheels found in dist")

    for wheel in wheels:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            unpack_dir = temp_dir / "unpacked"
            repacked_dir = temp_dir / "repacked"
            unpack_dir.mkdir()
            repacked_dir.mkdir()

            subprocess.run(
                [sys.executable, "-m", "wheel", "unpack", str(wheel), "--dest", str(unpack_dir)],
                check=True,
            )

            unpacked_items = [path for path in unpack_dir.iterdir() if path.is_dir()]
            if len(unpacked_items) != 1:
                raise SystemExit(f"Expected one unpacked wheel directory for {wheel.name}")

            wheel_root = unpacked_items[0]
            package_dir = wheel_root / "poptrie"
            if not package_dir.exists():
                raise SystemExit(f"poptrie package not found in {wheel.name}")
            dist_info_dirs = sorted(wheel_root.glob("*.dist-info"))
            if len(dist_info_dirs) != 1:
                raise SystemExit(f"Expected one dist-info directory for {wheel.name}")
            dist_info_dir = dist_info_dirs[0]
            public_dist_info_dir = wheel_root / f"{PACKAGE_NAME}-{public_version}.dist-info"

            suffixes = (".so", ".pyd", ".dll", ".dylib")
            for ext_file in wheel_root.iterdir():
                if ext_file.is_file() and ext_file.name.startswith("_native") and ext_file.suffix in suffixes:
                    target = package_dir / ext_file.name
                    if not target.exists():
                        shutil.move(str(ext_file), str(target))

            for source_path in package_src.iterdir():
                if source_path.is_file() and source_path.suffix == ".py":
                    shutil.copy2(source_path, package_dir / source_path.name)

            shutil.copy2(readme_src, wheel_root / "README.md")
            shutil.copy2(license_src, wheel_root / "LICENSE")
            (dist_info_dir / "METADATA").write_text(
                _render_metadata(public_version, readme_text),
                encoding="utf-8",
            )
            if dist_info_dir != public_dist_info_dir:
                dist_info_dir.rename(public_dist_info_dir)

            wheel.unlink()
            subprocess.run(
                [sys.executable, "-m", "wheel", "pack", str(wheel_root), "--dest-dir", str(repacked_dir)],
                check=True,
            )

            built_wheels = sorted(repacked_dir.glob("*.whl"))
            if len(built_wheels) != 1:
                raise SystemExit(f"Expected one repacked wheel for {wheel.name}")

            built_wheel = built_wheels[0]
            if public_version not in built_wheel.name:
                raise SystemExit(f"Repacked wheel version mismatch for {wheel.name}")
            shutil.copy2(built_wheel, dist_dir / built_wheel.name)


if __name__ == "__main__":
    main()
