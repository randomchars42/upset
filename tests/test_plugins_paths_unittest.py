"""Test plugin "Paths"."""

import logging
import logging.config
import pathlib
import sys
import unittest

from typing import Any
from unittest import mock
from upset import lib
from upset.plugins import paths

logging_handler: logging.StreamHandler = logging.StreamHandler()
logging_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(levelname)s %(name)s %(message)s')
logging_handler.setFormatter(formatter)
root_logger: logging.Logger = logging.getLogger()
root_logger.setLevel(logging.ERROR)
root_logger.addHandler(logging_handler)
logger: logging.Logger = logging.getLogger(__name__)

# pylint: disable=too-many-public-methods
class TestPluginsPaths(unittest.TestCase):
    """Test Paths from plugins."""

    def setUp(self) -> None:
        """Add some files."""
        self._base_dir: pathlib.Path = pathlib.Path('tests/tmp')
        try:
            self._base_dir.mkdir()
        except OSError:
            logger.debug('could not create "%s"', self._base_dir)

        self._task: Any = {
            'name': 'ensure my paths',
            'plugin': 'paths',
            'variables': {
                'paths': [
                    {
                        'path': '/home/$user/file',
                        'ensure': 'file',
                        'template': 'template2',
                        'mode': 'update',
                        'permissions': ['$user', '', 0o600],
                        'backup': True,
                    },
                    {
                        'path': '/home/$user/dir',
                        'ensure': 'dir',
                        'permissions': ['$user', '', 0o600],
                        'backup': True,
                    },
                    {
                        'path': '/home/$user/dir',
                        'target': '/home/$user/.hidden/dir',
                        'ensure': 'symlink',
                        'backup': True,
                    },
                ],
                'template1': {
                    'greeting': 'Greetings',
                    'caller': 'Admin',
                },
            },
            'foreach': ['user1', 'user2'],
            'foreach_variable': 'user',
            'files': {
                'template1': str(self._base_dir / 't'),
                'template2': '/template/with/variables',
            }
            }

        # create a mock argument containing the task so that
        # `lib.Plugins.get_data()` finds and decodes it
        with mock.patch.object(
                sys, 'argv',
                ['paths.py', lib.Helper.encode_data(self._task)]):
            self._paths = paths.Paths()

    def tearDown(self) -> None:
        """Remove files."""
        for file in self._base_dir.glob('*'):
            try:
                if file.is_dir():
                    file.rmdir()
                else:
                    file.unlink()
            except OSError:
                logger.debug('could not remove "%s"', file)
        try:
            self._base_dir.rmdir()
        except OSError:
            logger.debug('could not remove "%s"', self._base_dir)

    def test_ensure_absent(self) -> None:
        """Ensure file is absent by creating a backup."""
        pathlib.Path(self._base_dir / 'a').touch()
        #self._paths.ensure_absent(self._task['variables']['paths'][4])
        self._paths.ensure_absent({
            'path': str(self._base_dir / 'a'),
            'ensure': 'absent',
            'backup': True
            })
        self.assertTrue(pathlib.Path(self._base_dir / 'a~').exists())
        self.assertFalse(pathlib.Path(self._base_dir / 'a').exists())

    def test_ensure_file(self) -> None:
        """Ensure file exists."""
        pathlib.Path(self._base_dir / 't').write_text('$greeting, oh $caller!',
                encoding='utf-8')
        pathlib.Path(self._base_dir / 'a').touch()
        self._paths.ensure_file({
            'path': str(self._base_dir / 'a'),
            'ensure': 'file',
            'template': 'template1',
            'mode': 'force',
            'permissions': ['', '', 0o644],
            'backup': True
            })
        self.assertTrue(pathlib.Path(self._base_dir / 'a').exists())
        self.assertTrue(pathlib.Path(self._base_dir / 'a~').exists())
        self.assertEqual(
                pathlib.Path(self._base_dir / 'a').read_text(encoding='utf-8'),
                'Greetings, oh Admin!')
    def test_ensure_file_no_template(self) -> None:
        """Fail because no valid template exists."""
        with self.assertRaises(KeyError):
            self._paths.ensure_file({
                'path': str(self._base_dir / 'a'),
                'ensure': 'file',
                'template': 'template',
                'mode': 'force',
                'permissions': ['', '', 0o644],
                'backup': True
                })

    def test_ensure_link(self) -> None:
        """Ensure link exists."""
        pathlib.Path(self._base_dir / 't').touch()
        pathlib.Path(self._base_dir / 'a').touch()
        self._paths.ensure_symlink({
            'path': str(self._base_dir / 'a'),
            'ensure': 'symlink',
            'target': str(self._base_dir / 't'),
            'backup': True
            })
        self.assertTrue(pathlib.Path(self._base_dir / 'a').is_symlink())
        self.assertTrue(pathlib.Path(self._base_dir / 'a~').exists())

    def test_ensure_dir(self) -> None:
        """Ensure link exists."""
        pathlib.Path(self._base_dir / 'a').touch()
        self._paths.ensure_dir({
            'path': str(self._base_dir / 'a'),
            'ensure': 'dir',
            'permissions': ['', '', 0o644],
            'backup': True
            })
        self.assertTrue(pathlib.Path(self._base_dir / 'a').is_dir())
        self.assertTrue(pathlib.Path(self._base_dir / 'a~').exists())

    def test_ensure_in_file_append(self) -> None:
        """Ensure text occurs in a file."""
        pathlib.Path(self._base_dir / 'a').write_text('a',
                encoding='utf-8')
        lib.Fs.ensure_in_file(pathlib.Path(self._base_dir / 'a'),
                '\nc="b"', backup = True)
        self._paths.ensure_in_file({
            'path': str(self._base_dir / 'a'),
            'ensure': 'in_file',
            'text': '\nc="b"',
            'insert_at': '',
            'permissions': ['', '', 0o644],
            'backup': True
            })
        self.assertEqual(
                pathlib.Path(self._base_dir / 'a').read_text(encoding='utf-8'),
                'a\nc="b"')
        self.assertTrue(pathlib.Path(self._base_dir / 'a~').exists())

    def test_ensure_in_file_present(self) -> None:
        """Do nothing as the text is already in the file."""
        pathlib.Path(self._base_dir / 'a').write_text('a\nc="b"\nc',
                encoding='utf-8')
        self._paths.ensure_in_file({
            'path': str(self._base_dir / 'a'),
            'ensure': 'in_file',
            'text': '\nc="b"',
            'insert_at': '',
            'permissions': ['', '', 0o644],
            'backup': True
            })
        self.assertEqual(
                pathlib.Path(self._base_dir / 'a').read_text(encoding='utf-8'),
                'a\nc="b"\nc')
        self.assertFalse(pathlib.Path(self._base_dir / 'a~').exists())

    def test_ensure_in_file_replace(self) -> None:
        """Do nothing as the text is already in the file."""
        pathlib.Path(self._base_dir / 'a').write_text('a\nc="b"\nc',
                encoding='utf-8')
        self._paths.ensure_in_file({
            'path': str(self._base_dir / 'a'),
            'ensure': 'in_file',
            'text': '\nc="d"',
            'insert_at': '\nc="b"',
            'permissions': ['', '', 0o644],
            'backup': True
            })
        self.assertEqual(
                pathlib.Path(self._base_dir / 'a').read_text(encoding='utf-8'),
                'a\nc="d"\nc')
        self.assertTrue(pathlib.Path(self._base_dir / 'a~').exists())

if __name__ == '__main__':
    unittest.main()
