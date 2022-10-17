"""Test lib."""

import logging
import os
import pathlib
import time
import unittest

from upset import lib

logger: logging.Logger = logging.getLogger()

class TestLibFs(unittest.TestCase):
    """Test Fs from lib."""

    def setUp(self) -> None:
        """Add some files."""
        self._base_dir: pathlib.Path = pathlib.Path('tests/tmp')
        try:
            self._base_dir.mkdir()
        except OSError:
            logger.debug('could not create "%s"', self._base_dir)

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

    def test_backup_simple(self) -> None:
        """Create simple backup."""
        pathlib.Path(self._base_dir / 'a').touch()
        lib.Fs.backup(self._base_dir / 'a')
        self.assertTrue(pathlib.Path(self._base_dir / 'a~').exists())
        self.assertFalse(pathlib.Path(self._base_dir / 'a').exists())

    def test_backup_count_up(self) -> None:
        """Create simple backup if backup is present."""
        pathlib.Path(self._base_dir / 'b').touch()
        pathlib.Path(self._base_dir / 'b~').touch()
        lib.Fs.backup(self._base_dir / 'b')
        self.assertFalse(pathlib.Path(self._base_dir / 'b').exists())
        self.assertTrue(pathlib.Path(self._base_dir / 'b~').exists())
        self.assertTrue(pathlib.Path(self._base_dir / 'b~1~').exists())

    def test_backup_no_file(self) -> None:
        """Do nothing as no file exists."""
        lib.Fs.backup(self._base_dir / 'c')
        self.assertFalse(pathlib.Path(self._base_dir / 'c').exists())
        self.assertFalse(pathlib.Path(self._base_dir / 'c~').exists())

    def test_backup_directory(self) -> None:
        """Backup directory."""
        pathlib.Path(self._base_dir / 'd').mkdir()
        lib.Fs.backup(self._base_dir / 'd')
        self.assertTrue(pathlib.Path(self._base_dir / 'd~').exists())
        self.assertTrue(pathlib.Path(self._base_dir / 'd~').is_dir())

    def test_backup_symlink(self) -> None:
        """Do nothing as file is a symlink."""
        pathlib.Path(self._base_dir / 'f').touch()
        pathlib.Path(self._base_dir / 'e').symlink_to(self._base_dir / 'f')
        lib.Fs.backup(self._base_dir / 'e')
        self.assertFalse(pathlib.Path(self._base_dir / 'e~').exists())
        self.assertTrue(pathlib.Path(self._base_dir / 'e').is_symlink())

    def test_remove_backup(self) -> None:
        """Remove by creating a backup."""
        pathlib.Path(self._base_dir / 'a').touch()
        lib.Fs.remove(self._base_dir / 'a', backup=True)
        self.assertTrue(pathlib.Path(self._base_dir / 'a~').exists())
        self.assertFalse(pathlib.Path(self._base_dir / 'a').exists())

    def test_remove_simple(self) -> None:
        """Remove file."""
        pathlib.Path(self._base_dir / 'a').touch()
        lib.Fs.remove(self._base_dir / 'a', backup=False)
        self.assertFalse(pathlib.Path(self._base_dir / 'a').exists())
        self.assertFalse(pathlib.Path(self._base_dir / 'a~').exists())

    def test_remove_no_file(self) -> None:
        """Do nothing as no file exists."""
        # should do nothing as b does not exist
        lib.Fs.remove(self._base_dir / 'b')
        self.assertFalse(pathlib.Path(self._base_dir / 'b~').exists())

    def test_remove_directory(self) -> None:
        """Remove directory."""
        pathlib.Path(self._base_dir / 'a').mkdir()
        lib.Fs.remove(self._base_dir / 'a', backup=False)
        self.assertFalse(pathlib.Path(self._base_dir / 'a').exists())
        self.assertFalse(pathlib.Path(self._base_dir / 'a~').exists())

    def test_remove_symlink(self) -> None:
        """Remove symlink."""
        pathlib.Path(self._base_dir / 'b').touch()
        pathlib.Path(self._base_dir / 'a').symlink_to(self._base_dir / 'b')
        lib.Fs.remove(self._base_dir / 'a')
        self.assertFalse(pathlib.Path(self._base_dir / 'a').exists())

    def test_ensure_file(self) -> None:
        """Ensure file exists."""
        pathlib.Path(self._base_dir / 't').write_text('$greeting, oh $user!',
                encoding='utf-8')
        pathlib.Path(self._base_dir / 'a').touch()
        lib.Fs.ensure_file(pathlib.Path(self._base_dir / 'a'),
                lib.Template(file=pathlib.Path(self._base_dir / 't'),
                    substitutes = {'user': 'admin', 'greeting': 'Greetings'}),
                lib.PermissionSet(owner = '', group = '', mode = 0o644),
                mode = 'force', backup = True)
        self.assertTrue(pathlib.Path(self._base_dir / 'a').exists())
        self.assertTrue(pathlib.Path(self._base_dir / 'a~').exists())
        self.assertEqual(
                pathlib.Path(self._base_dir / 'a').read_text(encoding='utf-8'),
                'Greetings, oh admin!')

    def test_ensure_file_update(self) -> None:
        """Ensure file exists and is updated."""
        pathlib.Path(self._base_dir / 'a').write_text('Hello!',
                encoding='utf-8')
        pathlib.Path(self._base_dir / 't').write_text('$greeting, oh $user!',
                encoding='utf-8')
        lib.Fs.ensure_file(pathlib.Path(self._base_dir / 'a'),
                lib.Template(file=pathlib.Path(self._base_dir / 't'),
                    substitutes = {'user': 'admin', 'greeting': 'Greetings'}),
                lib.PermissionSet(owner = '', group = '', mode = 0o644),
                mode = 'update', backup = True)
        self.assertTrue(pathlib.Path(self._base_dir / 'a').exists())
        self.assertTrue(pathlib.Path(self._base_dir / 'a~').exists())
        self.assertEqual(
                pathlib.Path(self._base_dir / 'a').read_text(encoding='utf-8'),
                'Greetings, oh admin!')

    def test_ensure_file_no_update(self) -> None:
        """Ensure file exists but is not updated."""
        pathlib.Path(self._base_dir / 't').write_text('$greeting, oh $user!',
                encoding='utf-8')
        fake_time: float = time.time() - 2
        os.utime(str(pathlib.Path(self._base_dir / 't')),
                (fake_time, fake_time))
        pathlib.Path(self._base_dir / 'a').write_text('Hello!',
                encoding='utf-8')
        lib.Fs.ensure_file(pathlib.Path(self._base_dir / 'a'),
                lib.Template(file=pathlib.Path(self._base_dir / 't'),
                    substitutes = {'user': 'admin', 'greeting': 'Greetings'}),
                lib.PermissionSet(owner = '', group = '', mode = 0o644),
                mode = 'update', backup = True)
        self.assertTrue(pathlib.Path(self._base_dir / 'a').exists())
        self.assertFalse(pathlib.Path(self._base_dir / 'a~').exists())
        self.assertEqual(
                pathlib.Path(self._base_dir / 'a').read_text(encoding='utf-8'),
                'Hello!')

    def test_ensure_file_as_is(self) -> None:
        """Ensure file exists but is left as is."""
        pathlib.Path(self._base_dir / 't').write_text('$greeting, oh $user!',
                encoding='utf-8')
        pathlib.Path(self._base_dir / 'a').write_text('Hello!',
                encoding='utf-8')
        lib.Fs.ensure_file(pathlib.Path(self._base_dir / 'a'),
                lib.Template(file=pathlib.Path(self._base_dir / 't'),
                    substitutes = {'user': 'admin', 'greeting': 'Greetings'}),
                lib.PermissionSet(owner = '', group = '', mode = 0o644),
                mode = 'asis', backup = True)
        self.assertTrue(pathlib.Path(self._base_dir / 'a').exists())
        self.assertFalse(pathlib.Path(self._base_dir / 'a~').exists())
        self.assertEqual(
                pathlib.Path(self._base_dir / 'a').read_text(encoding='utf-8'),
                'Hello!')

    def test_ensure_file_no_template(self) -> None:
        """Fail because no valid template exists."""
        pathlib.Path(self._base_dir / 'a').touch()
        with self.assertRaises(lib.UpsetFsError):
            lib.Fs.ensure_file(pathlib.Path(self._base_dir / 'a'),
                    lib.Template(file=pathlib.Path(self._base_dir / 't'),
                        substitutes = {}),
                    lib.PermissionSet(owner = '', group = '', mode = 0o644),
                    mode = 'force', backup = True)
        pathlib.Path(self._base_dir / 't').mkdir()
        with self.assertRaises(lib.UpsetFsError):
            lib.Fs.ensure_file(pathlib.Path(self._base_dir / 'a'),
                    lib.Template(file=pathlib.Path(self._base_dir / 't'),
                        substitutes = {}),
                    lib.PermissionSet(owner = '', group = '', mode = 0o644),
                    mode = 'force', backup = True)

    def test_ensure_link(self) -> None:
        """Ensure link exists."""
        pathlib.Path(self._base_dir / 't').touch()
        pathlib.Path(self._base_dir / 'a').touch()
        lib.Fs.ensure_link(pathlib.Path(self._base_dir / 'a'),
                pathlib.Path(self._base_dir / 't'), backup = True)
        self.assertTrue(pathlib.Path(self._base_dir / 'a').is_symlink())
        self.assertTrue(pathlib.Path(self._base_dir / 'a~').exists())

    def test_ensure_dir(self) -> None:
        """Ensure link exists."""
        pathlib.Path(self._base_dir / 'a').touch()
        lib.Fs.ensure_dir(pathlib.Path(self._base_dir / 'a'),
                lib.PermissionSet(), backup = True)
        self.assertTrue(pathlib.Path(self._base_dir / 'a').is_dir())
        self.assertTrue(pathlib.Path(self._base_dir / 'a~').exists())

    def test_ensure_in_file_append(self) -> None:
        """Ensure text occurs in a file."""
        pathlib.Path(self._base_dir / 'a').write_text('a',
                encoding='utf-8')
        lib.Fs.ensure_in_file(pathlib.Path(self._base_dir / 'a'),
                r'\nc="b"', backup = True)
        self.assertEqual(
                pathlib.Path(self._base_dir / 'a').read_text(encoding='utf-8'),
                'a\nc="b"')
        self.assertTrue(pathlib.Path(self._base_dir / 'a~').exists())

    def test_ensure_in_file_present(self) -> None:
        """Do nothing as the text is already in the file."""
        pathlib.Path(self._base_dir / 'a').write_text('a\nc="b"\nc',
                encoding='utf-8')
        lib.Fs.ensure_in_file(pathlib.Path(self._base_dir / 'a'),
                r'\nc="b"', backup = True)
        self.assertEqual(
                pathlib.Path(self._base_dir / 'a').read_text(encoding='utf-8'),
                'a\nc="b"\nc')
        self.assertFalse(pathlib.Path(self._base_dir / 'a~').exists())

    def test_ensure_in_file_replace(self) -> None:
        """Do nothing as the text is already in the file."""
        pathlib.Path(self._base_dir / 'a').write_text('a\nc="b"\nc',
                encoding='utf-8')
        lib.Fs.ensure_in_file(pathlib.Path(self._base_dir / 'a'),
                r'c="d"', insert_at = r'c="b"', backup = True)
        self.assertEqual(
                pathlib.Path(self._base_dir / 'a').read_text(encoding='utf-8'),
                'a\nc="d"\nc')
        self.assertTrue(pathlib.Path(self._base_dir / 'a~').exists())

if __name__ == '__main__':
    unittest.main()
