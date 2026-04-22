#!/usr/bin/env python
"""Build script for Cython extensions."""

from __future__ import annotations

from pathlib import Path

from Cython.Build import cythonize  # type: ignore[import-untyped]
from setuptools import Extension, setup  # type: ignore[import-untyped]

# Get the project root directory (parent of scripts/)
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent

# Define the extension
ext = Extension(
    "vibe.core.fuzzy.history_fuzzy",
    [str(project_root / "vibe/core/fuzzy/history_fuzzy.pyx")],
)

# Build the extension in-place - explicitly disable config file reading
setup(
    name="mistral-vibe",
    ext_modules=cythonize(
        [ext],
        language_level=3,
        compiler_directives={
            "language_level": 3,
            "binding": True,
            "boundscheck": False,
            "wraparound": False,
            "cdivision": True,
            "initializedcheck": False,
            "infer_types": True,
        },
    ),
    packages=[],  # Disable package discovery
    package_dir={},  # Disable package discovery
    script_args=["build_ext", "--inplace"],
)
