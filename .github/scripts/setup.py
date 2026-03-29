from pathlib import Path

from setuptools import Distribution, find_packages, setup


class BinaryDistribution(Distribution):
    def has_ext_modules(self):
        return True


README = Path(__file__).resolve().parent / "README.md"

setup(
    name="poptrie",
    version="__VERSION__",
    distclass=BinaryDistribution,
    description="High-performance IP and country lookup backed by Rust poptrie",
    long_description=README.read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    author="HarmonSir",
    author_email="git@pylab.me",
    license="Apache-2.0",
    url="https://github.com/swoiow/poptrie-pub",
    project_urls={
        "Source": "https://github.com/swoiow/poptrie-pub",
        "Issues": "https://github.com/swoiow/poptrie-pub/issues",
        "Releases": "https://github.com/swoiow/poptrie-pub/releases",
    },
    classifiers=[
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
    ],
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "poptrie": ["*.so", "*.pyd", "*.dll", "*.dylib"],
    },
)
