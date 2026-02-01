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


def _parse_wheel_tags(filename: str) -> tuple[str, str, str]:
    name = filename
    if name.endswith(".whl"):
        name = name[:-4]
    parts = name.split("-")
    if len(parts) < 5:
        raise SystemExit(f"Invalid wheel filename: {filename}")
    return parts[-3], parts[-2], parts[-1]


def main() -> None:
    repo_root = Path.cwd()
    dist_dir = repo_root / "dist"
    cargo_toml = repo_root / "Cargo.toml"
    build_src = repo_root / "build_bin.py"
    ipsearcher_src = repo_root / "example_production.py"
    setup_template = repo_root / ".github" / "scripts" / "setup.py"

    if not cargo_toml.exists():
        raise SystemExit("Cargo.toml not found")
    if not build_src.exists():
        raise SystemExit("build_bin.py not found")
    if not ipsearcher_src.exists():
        raise SystemExit("example_production.py not found")
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

        shutil.copy2(build_src, package_dir / "build.py")
        shutil.copy2(ipsearcher_src, package_dir / "ipsearcher.py")
        (temp_dir / "setup.py").write_text(setup_py, encoding="utf-8")

        wheel.unlink()
        python_tag, abi_tag, plat_tag = _parse_wheel_tags(wheel.name)
        subprocess.run(
            [
                sys.executable,
                "setup.py",
                "bdist_wheel",
                "--python-tag",
                python_tag,
                "--abi-tag",
                abi_tag,
                "--plat-name",
                plat_tag,
            ],
            cwd=temp_dir,
            check=True,
        )
        built_wheels = sorted((temp_dir / "dist").glob("*.whl"))
        if not built_wheels:
            raise SystemExit("bdist_wheel did not produce a wheel")
        for built_wheel in built_wheels:
            shutil.copy2(built_wheel, dist_dir / built_wheel.name)
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    main()
