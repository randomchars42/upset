"""Test lib."""

import getpass
import logging
import logging.config
import os
import pathlib
import socket
import time
import unittest

from upset import lib

# create console handler and set level to debug
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

    def test_ensure_in_file_no_file_append(self) -> None:
        """Ensure text occurs in a non-existent file."""
        lib.Fs.ensure_in_file(pathlib.Path(self._base_dir / 'a'),
                r'\nc="b"', backup = True)
        self.assertEqual(
                pathlib.Path(self._base_dir / 'a').read_text(encoding='utf-8'),
                '\nc="b"')

    def test_ensure_in_file_no_file_replace(self) -> None:
        """Do nothing because no text occurs in a non-existent file."""
        lib.Fs.ensure_in_file(pathlib.Path(self._base_dir / 'a'),
                r'c="d"', insert_at = r'c="b"', backup = True)
        self.assertEqual(
                pathlib.Path(self._base_dir / 'a').read_text(encoding='utf-8'),
                '')

# pylint: disable=too-many-public-methods
class TestLibSys(unittest.TestCase):
    """Test Sys from lib."""

    def setUp(self) -> None:
        """Add test directory and instantiate class."""
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

    def test_run_command(self) -> None:
        """Run command."""
        self.assertEqual(
                lib.Sys.run_command(['bash', '-c', 'echo Hello']),
                'Hello')

    def test_run_command_fail(self) -> None:
        """Fail running a command."""
        with self.assertRaises(lib.UpsetSysError):
            lib.Sys.run_command(['cp', '--fail'])

    def test_build_command_run(self) -> None:
        """Run command."""
        self.assertEqual(
                lib.Sys.run_command(
                    lib.Sys.build_command(['echo "Hello"'])),
                'Hello')

    def test_build_sudo_command(self) -> None:
        """Build sudo command sequence."""
        self.assertEqual(
                lib.Sys.build_sudo_command(['echo', '"Hello"'], 'password'),
                ['bash', '-c',
                    'echo ZWNobyAicGFzc3dvcmQiIHwgc3VkbyAtUyAtLXByb21wdD0gLS0'\
                            'gZWNobyAiSGVsbG8iCg== | '\
                            'base64 -d | $SHELL'])

    @unittest.skipUnless(require_interaction,
            'do not require interaction with the user')
    def test_build_sudo_command_run(self) -> None:
        """Run sudo command sequence."""
        self.assertEqual(
                lib.Sys.run_command(
                    lib.Sys.build_sudo_command(['echo', 'Hello'],
                        getpass.getpass())),
                'Hello')

    def test_build_scp_command_to(self) -> None:
        """Build scp command sequence."""
        file_a: pathlib.Path = pathlib.Path('a')
        file_b: pathlib.Path = pathlib.Path('b')
        self.assertEqual(
                lib.Sys.build_scp_command(file_a, file_b, 'to', 'test', 'host',
                    ssh_key=pathlib.Path('ssh_key')),
                ['scp', '-i', 'ssh_key', '-p', 'a',
                    'test@host:/b'])

    def test_build_scp_command_from(self) -> None:
        """Build scp command sequence."""
        file_a: pathlib.Path = pathlib.Path('a')
        file_b: pathlib.Path = pathlib.Path('b')
        self.assertEqual(
                lib.Sys.build_scp_command(file_a, file_b, 'from', 'test',
                    'host', ssh_key=pathlib.Path('ssh_key')),
                ['scp', '-i', 'ssh_key', '-p', 'test@host:/b',
                    'a'])

    def test_build_scp_command_run(self) -> None:
        """Run scp command sequence."""
        file_a: pathlib.Path = pathlib.Path(self._base_dir / 'a')
        file_b: pathlib.Path = pathlib.Path(self._base_dir / 'b')
        file_a.touch()
        self.assertTrue(file_a.exists())
        lib.Sys.run_command(
                lib.Sys.build_scp_command(file_a, file_b))
        self.assertTrue(file_a.exists())
        self.assertTrue(file_b.exists())

    def test_make_temporary_directory(self) -> None:
        """Create a temporary directory."""
        temp_dir: pathlib.Path = lib.Sys.make_temporary_directory()
        self.assertTrue(temp_dir.exists())
        temp_dir.rmdir()

    def test_remove_temporary_directory(self) -> None:
        """Remove a temporary directory."""
        temp_dir: pathlib.Path = pathlib.Path(self._base_dir / 'tmp')
        temp_dir.mkdir()
        pathlib.Path(self._base_dir / 'tmp' / 'a').touch()
        self.assertTrue(temp_dir.is_dir())
        lib.Sys.remove_temporary_directory(temp_dir)
        self.assertFalse(temp_dir.exists())

    @unittest.skipUnless(require_interaction,
            'do not require interaction with the user')
    def test_ensure_ssh(self) -> None:
        """Ensure ssh key exists"""
        ssh_key: pathlib.Path = self._base_dir / 'key'
        pub_ssh_key: pathlib.Path = self._base_dir / 'key.pub'
        authorized_keys = self._base_dir / 'authorized_keys'
        lib.Sys.ensure_ssh_key(getpass.getuser(), socket.gethostname(),
                ssh_key, self._base_dir.resolve())
        self.assertTrue(ssh_key.exists())
        self.assertTrue(authorized_keys.exists())
        self.assertEqual(
                pub_ssh_key.read_text(encoding='utf-8').strip(),
                authorized_keys.read_text(encoding='utf-8').strip())
        lib.Sys.ensure_ssh_key_absent(getpass.getuser(), socket.gethostname(),
                ssh_key, self._base_dir.resolve(), False)
        self.assertFalse(ssh_key.exists())
        self.assertEqual('',
                authorized_keys.read_text(encoding='utf-8').strip())

# pylint: disable=too-many-public-methods
class TestLibHelper(unittest.TestCase):
    """Test Sys from lib."""

    def setUp(self) -> None:
        """Add test directory and instantiate class."""
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

    def test_create_unique_filename(self) -> None:
        """Create a unique filename."""
        name: str = lib.Helper.create_unique_file_name(
                pathlib.Path('/home/test/a'))
        self.assertEqual(name, 'home___test___a')

    def test_localise_plugin(self) -> None:
        """Localise a plugin."""
        pathlib.Path(self._base_dir / 'a.py').touch()
        self.assertEqual(
                lib.Helper.localise_plugin('a', [self._base_dir]),
                self._base_dir / 'a.py')

    def test_encode_data(self) -> None:
        """Encode data."""
        self.assertEqual(
                lib.Helper.encode_data({'greeting': 'hello'}),
                'eyJncmVldGluZyI6ICJoZWxsbyJ9')

    def test_encode_data_fail(self) -> None:
        """Fail encoding data."""
        with self.assertRaises(lib.UpsetHelperError):
            lib.Helper.encode_data(pathlib.Path('not/serialiseable'))

    def test_decode_data(self) -> None:
        """Decode data."""
        self.assertEqual(
                lib.Helper.decode_data('eyJncmVldGluZyI6ICJoZWxsbyJ9'),
                {'greeting': 'hello'})

if __name__ == '__main__':
    unittest.main()
