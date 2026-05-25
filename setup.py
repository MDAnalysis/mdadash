import shutil
import subprocess
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist


def _build_frontend():
    frontend_dir = Path(__file__).parent / "mdadash" / "frontend"
    subprocess.run(["npm", "ci"], cwd=frontend_dir, check=True)
    subprocess.run(["npm", "run", "build"], cwd=frontend_dir, check=True)


class _sdist(sdist):
    def run(self):
        root_dir = Path(__file__).parent
        node_modules = root_dir / "mdadash" / "frontend" / "node_modules"
        # Move the node_modules temporarily if it exists to prevent it from
        # becoming part of the final source distribution
        tmp_node_modules = root_dir / ".tmp.frontend.node_modules"
        node_modules_exists = node_modules.exists()
        if node_modules_exists:
            shutil.move(str(node_modules), str(tmp_node_modules))
        try:
            _build_frontend()
            super().run()
        finally:
            # Restore any existing node_modules moved earlier
            if node_modules_exists and tmp_node_modules.exists():
                shutil.move(str(tmp_node_modules), str(node_modules))


class _build_py(build_py):
    def run(self):
        dist = Path(__file__).parent / "mdadash" / "frontend" / "dist"
        if not dist.exists():
            # Don't build frontend again after sdist
            _build_frontend()
        super().run()


setup(
    cmdclass={
        "sdist": _sdist,
        "build_py": _build_py,
    },
)
