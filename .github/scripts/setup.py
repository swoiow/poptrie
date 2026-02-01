from setuptools import find_packages, setup
from setuptools.dist import Distribution


class BinaryDistribution(Distribution):
    def has_ext_modules(self) -> bool:
        return True


setup(
    name="poptrie",
    version="__VERSION__",
    description="Fast IP lookup using poptrie",
    author="HarmonSir",
    author_email="git@pylab.me",
    license="Apache-2.0",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "poptrie": ["*.so", "*.pyd", "*.dll", "*.dylib"],
    },
    distclass=BinaryDistribution,
)
