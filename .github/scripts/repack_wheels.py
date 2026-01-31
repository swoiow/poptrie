"""
if you want to repack with details, please check the git log, before “less code repack, make it simple.”
"""

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def _read_version(cargo_toml: Path) -> str:
    for line in cargo_toml.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("version"):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("Version not found in Cargo.toml")


def _load_setup_template(template_path: Path, version: str) -> str:
    template = template_path.read_text(encoding="utf-8")
    if "__VERSION__" not in template:
        raise SystemExit("setup.py template missing __VERSION__ placeholder")
    return template.replace("__VERSION__", version)


def main() -> None:
    repo_root = Path.cwd()
    private_root = Path(os.environ["POPTRIE_PRIVATE_SRC"])
    dist_dir = repo_root / os.environ.get("POPTRIE_DIST_DIR", "dist")
    cargo_toml = private_root / "Cargo.toml"
    ipsearcher_src = repo_root / "ip_searcher.py"
    setup_template = repo_root / ".github" / "scripts" / "setup.py"

    if not cargo_toml.exists():
        raise SystemExit("Cargo.toml not found")
    if not ipsearcher_src.exists():
        raise SystemExit("ip_searcher.py not found")
    if not setup_template.exists():
        raise SystemExit("setup.py template not found")

    version = _read_version(cargo_toml)
    setup_py = _load_setup_template(setup_template, version)

    wheels = sorted(dist_dir.glob("*.whl"))
    if not wheels:
        raise SystemExit("No wheels found in dist")

    for wheel in wheels:
        temp_dir = Path(tempfile.mkdtemp())
        with zipfile.ZipFile(wheel, "r") as zf:
            zf.extractall(temp_dir)
        package_dir = temp_dir / "poptrie"
        if not package_dir.exists():
            raise SystemExit(f"poptrie package not found in {wheel.name}")
        suffixes = (".so", ".pyd", ".dll", ".dylib")
        for ext_file in temp_dir.iterdir():
            if ext_file.is_file() and ext_file.name.startswith("poptrie") and ext_file.suffix in suffixes:
                target = package_dir / ext_file.name
                if not target.exists():
                    shutil.move(str(ext_file), str(target))

        shutil.copy2(ipsearcher_src, package_dir / "ip_searcher.py")
        (temp_dir / "setup.py").write_text(setup_py, encoding="utf-8")

        wheel.unlink()
        subprocess.run(
            [sys.executable, "setup.py", "bdist_wheel", "--py-limited-api=cp38"],
            cwd=temp_dir,
            check=True,
        )
        built_wheels = sorted((temp_dir / "dist").glob("*.whl"))
        if not built_wheels:
            raise SystemExit("bdist_wheel did not produce a wheel")
        if sys.platform.startswith("linux"):
            wheelhouse = temp_dir / "wheelhouse"
            wheelhouse.mkdir(exist_ok=True)
            for built_wheel in built_wheels:
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "auditwheel",
                        "repair",
                        str(built_wheel),
                        "-w",
                        str(wheelhouse),
                    ],
                    cwd=temp_dir,
                    check=True,
                )
            repaired = sorted(wheelhouse.glob("*.whl"))
            if not repaired:
                raise SystemExit("auditwheel did not produce a wheel")
            for built_wheel in repaired:
                shutil.copy2(built_wheel, dist_dir / built_wheel.name)
        else:
            for built_wheel in built_wheels:
                shutil.copy2(built_wheel, dist_dir / built_wheel.name)
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    main()
