"""Setup shim - build config lives in pyproject.toml."""
from setuptools import find_packages, setup

setup(
    name="anygamevoice",
    version="0.1.0",
    packages=find_packages(include=["app*", "plugins*"]),
)
