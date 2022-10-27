"""Test plugin "Paths"."""

import logging
import os
import sys
import unittest

from typing import Any
from unittest import mock
from upset import lib
from upset.plugins import users

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
require_interaction: bool = bool(os.environ.get('UPSET_INTERACTION', 0))

# pylint: disable=too-many-public-methods
class TestPluginsUsers(unittest.TestCase):
    """Test Users from plugins."""

    def setUp(self) -> None:
        """Add some files."""
        self._task: Any = {
            'name': 'ensure my users',
            'plugin': 'users',
            }

        # create a mock argument containing the task so that
        # `lib.Plugins.get_data()` finds and decodes it
        with mock.patch.object(
                sys, 'argv',
                ['users.py', lib.Helper.encode_data(self._task)]):
            self._users = users.Users()

    def tearDown(self) -> None:
        """Remove files."""

    def test_user_exists(self) -> None:
        """Test if user exists"""
        self.assertTrue(self._users.user_exists('root'))
        self.assertFalse(self._users.user_exists('!kitty'))

    def test_group_exists(self) -> None:
        """Test if group exists"""
        self.assertTrue(self._users.group_exists('root'))
        self.assertFalse(self._users.group_exists('!kitty'))

    def test_user_in_group(self) -> None:
        """Test if user is in group"""
        self.assertTrue(self._users.user_in_group('root', 'root'))
        self.assertFalse(self._users.user_in_group('root', 'audio'))

    def test_user_in_group_fail(self) -> None:
        """Fail testing if user is in group"""
        with self.assertRaises(lib.UpsetError):
            self._users.user_in_group('root', '!kitty')
        with self.assertRaises(lib.UpsetError):
            self._users.user_in_group('!kitty', 'root')

    @unittest.skipUnless(require_interaction,
            'do not require interaction with the user')
    def test_ensure_user(self) -> None:
        """Ensure user exists / does not exist."""
        self._users.ensure_user('root')
        self._users.user_exists('root')
        self._users.ensure_user(name='upsettestuser',
                group='root',
                gecos='Upset Test User,,,,',
                password='$1$FLV0AoCl$sPzvwJwKLMm2wXfmCYUYk1')
        self.assertTrue(self._users.user_exists('upsettestuser'))
        self._users.ensure_user_absent('upsettestuser')
        self.assertFalse(self._users.user_exists('upsettestuser'))

    @unittest.skipUnless(require_interaction,
            'do not require interaction with the user')
    def test_ensure_group(self) -> None:
        """Ensure group exists / does not exist."""
        self._users.ensure_group('root')
        self._users.group_exists('root')
        self._users.ensure_group('upsettestgroup')
        self.assertTrue(self._users.group_exists('upsettestgroup'))
        self._users.ensure_group_absent('upsettestgroup')
        self.assertFalse(self._users.group_exists('upsettestgroup'))

    @unittest.skipUnless(require_interaction,
            'do not require interaction with the user')
    def test_ensure_in_group(self) -> None:
        """Ensure user is / is not in group."""
        self._users.ensure_in_group('root', 'root')
        self.assertTrue(self._users.user_in_group('root', 'root'))
        self._users.user_in_group('root', 'games')
        self.assertFalse(self._users.user_in_group('root', 'games'))
        self._users.ensure_in_group('root', 'games')
        self.assertTrue(self._users.user_in_group('root', 'games'))
        self._users.ensure_not_in_group('root', 'games')
        self.assertFalse(self._users.user_in_group('root', 'games'))

if __name__ == '__main__':
    unittest.main()
