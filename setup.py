"""Build the Python package together with the offline studio resources."""

from pathlib import Path
import shutil

from setuptools import find_packages, setup
from setuptools.command.build_py import build_py


class BuildPy(build_py):
    """Keep ui/ as the source directory while shipping assets inside app/."""

    def run(self):
        super().run()
        root = Path(__file__).resolve().parent
        for resource in ('ui', 'examples', 'voices/presets'):
            source = root / resource
            if source.is_dir():
                shutil.copytree(source, Path(self.build_lib) / 'app' / '_resources' / resource,
                                dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))

    def get_outputs(self, include_bytecode=1):
        outputs = super().get_outputs(include_bytecode)
        resources = Path(self.build_lib) / 'app' / '_resources'
        if resources.is_dir():
            outputs.extend(str(path) for path in resources.rglob('*') if path.is_file())
        return outputs


setup(packages=find_packages(include=['app*', 'plugins*']), cmdclass={'build_py': BuildPy})
