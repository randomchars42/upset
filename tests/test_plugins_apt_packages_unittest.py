"""Test plugin "Paths"."""

import logging
import os
import pathlib
import sys
import time
import unittest

from typing import Any
from unittest import mock
from upset import lib
from upset.plugins import apt_packages

logging_handler: logging.StreamHandler = logging.StreamHandler()
logging_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(levelname)s %(name)s %(message)s')
logging_handler.setFormatter(formatter)
root_logger: logging.Logger = logging.getLogger()
root_logger.setLevel(logging.ERROR)
root_logger.addHandler(logging_handler)
logger: logging.Logger = logging.getLogger(__name__)

levels: list[str] = ['ERROR', 'WARNING', 'INFO', 'DEBUG']
# there are only levels 0 to 3
# everything else will cause the index to be out of bounds
root_logger.setLevel(
        levels[min(int(os.environ.get('UPSET_VERBOSITY', 1)), 3)])
# enable tests that need interaction with the user
require_interaction: bool = bool(int(os.environ.get('UPSET_INTERACTION', 0)))

# pylint: disable=too-many-public-methods
class TestPluginsAptPackages(unittest.TestCase):
    """Test AptPackages from plugins."""

    def setUp(self) -> None:
        """Create task, mock params."""
        self._task: Any = {
            'name': 'ensure my apt packages',
            'plugin': 'apt_packages',
            }

        # create a mock argument containing the task so that
        # `lib.Plugins.get_data()` finds and decodes it
        with mock.patch.object(
                sys, 'argv',
                ['apt_paths.py', lib.Helper.encode_data(self._task)]):
            self._apt_packages = apt_packages.AptPackages()

    def tearDown(self) -> None:
        """Remove files."""

    def test_package_installed(self) -> None:
        """Test if a package is installed."""
        self.assertTrue(self._apt_packages.package_installed('apt'))
        self.assertFalse(self._apt_packages.package_installed('!kitty'))

    @unittest.skipUnless(require_interaction,
            'do not require interaction with the user')
    def test_ensure_package(self) -> None:
        """Ensure a package is installed."""
        self._apt_packages.ensure_packages(['apt', 'sshpass'])
        self.assertTrue(self._apt_packages.package_installed('apt'))
        self.assertTrue(self._apt_packages.package_installed('sshpass'))
        self._apt_packages.ensure_packages_absent(['sshpass'])
        self.assertFalse(self._apt_packages.package_installed('sshpass'))

    @unittest.skipUnless(require_interaction,
            'do not require interaction with the user')
    def test_apt_do(self) -> None:
        """Ensure repositories are up to date."""
        self._apt_packages.apt_do('update')
        # determine last update
        # https://askubuntu.com/questions/410247/#410259
        last_update: float = pathlib.Path(
                '/var/cache/apt/pkgcache.bin').stat().st_mtime
        self.assertTrue(last_update > time.time() - 60)
        with self.assertRaises(lib.UpsetError):
            self._apt_packages.apt_do('something stupid')

if __name__ == '__main__':
    unittest.main()
