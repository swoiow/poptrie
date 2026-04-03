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
    repo_root = Path(os.environ.get("GITHUB_WORKSPACE", Path.cwd())).resolve()
    private_root = Path(os.environ["POPTRIE_PRIVATE_SRC"]).resolve()
    dist_dir = repo_root / os.environ.get("POPTRIE_DIST_DIR", "dist")
    cargo_toml = private_root / "Cargo.toml"
    package_src = repo_root / "poptrie"
    readme_src = repo_root / "README.md"
    license_src = repo_root / "LICENSE"
    setup_template = repo_root / ".github" / "scripts" / "setup.py"

    if not cargo_toml.exists():
        raise SystemExit("Cargo.toml not found")
    if not package_src.exists():
        raise SystemExit("poptrie package directory not found")
    if not readme_src.exists():
        raise SystemExit("README.md not found")
    if not license_src.exists():
        raise SystemExit("LICENSE not found")
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
            if ext_file.is_file() and ext_file.name.startswith("_native") and ext_file.suffix in suffixes:
                target = package_dir / ext_file.name
                if not target.exists():
                    shutil.move(str(ext_file), str(target))

        for source_path in package_src.iterdir():
            if source_path.is_file() and source_path.suffix == ".py":
                shutil.copy2(source_path, package_dir / source_path.name)
        shutil.copy2(readme_src, temp_dir / "README.md")
        shutil.copy2(license_src, temp_dir / "LICENSE")
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
