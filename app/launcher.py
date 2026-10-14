"""PyInstaller entry point: absolute import of the package (relative imports in __main__ need a parent package)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from galaxyxr_vrlink.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
