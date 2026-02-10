from setuptools import Distribution, find_packages, setup


class BinaryDistribution(Distribution):
    def has_ext_modules(self):
        return True


setup(
    name="poptrie",
    version="__VERSION__",
    distclass=BinaryDistribution,
    description="Fast IP lookup using poptrie",
    author="HarmonSir",
    author_email="git@pylab.me",
    license="Apache-2.0",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "poptrie": ["*.so", "*.pyd", "*.dll", "*.dylib"],
    },
)
