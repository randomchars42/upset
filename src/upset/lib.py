"""Library providing basic functionality and a base class for plugins."""

import configparser
import dataclasses
import grp
import logging
import os
import pathlib
import pwd
import re
import stat
import string

logger: logging.Logger = logging.getLogger()

@dataclasses.dataclass
class Template():
    """Holds a template string and its variables.

    Attributes:
        string: The file with `$variables` to use as content.
        substitutes: A dictionary with the variable names as keys and their
            substitutes as values.
    """
    file: pathlib.Path
    substitutes: dict[str, str]

@dataclasses.dataclass
class PermissionSet():
    """Holds a basic representation of UNIX permissions.

    Attributes:
        mod: The file mode (octal value; default `0o600`).
        owner: The file owner (existence will be checked; `''` to leave as is).
        group: The group (existence will not be checked; `''` to leave as is).
    """
    mode: int = 0o600
    owner: str = ''
    group: str = ''

class UpsetFsError(Exception):
    """Error for Fs interactions."""

class Fs:
    """Filesystem related functions."""

    @staticmethod
    def backup(path: pathlib.Path, number: int = 0) -> None:
        """Backup a file by moving it to "FILENAME~" or "FILENAME~NUM~".

        Args:
            path: The path to the file to backup.
            number: The number of the backup. Do not change this.

        Raises:
            UpsetFsError: If filesystem interaction fails.
        """
        if not (path.is_file() or path.is_dir()):
            return

        suffix: str = f'~{number}~' if number > 0 else '~'
        backup_path: pathlib.Path = pathlib.Path(str(path) + suffix)

        if backup_path.exists():
            Fs.backup(path, number + 1)
            return

        logger.info('creating backup for %s', str(path))
        try:
            path.rename(backup_path)
        except OSError as error:
            raise UpsetFsError(f'could not backup "{path}"') from error

    @staticmethod
    def remove(path: pathlib.Path, backup: bool = True) -> None:
        """Remove the file or move it to "FILENAME(.SUFFIX).bk".

        Args:
            path: The path to ensure a file.
            backup: Create a backup (see `Fs.backup()`).

        Raises:
            UpsetFsError: If filesystem interaction fails.
        """
        if backup:
            Fs.backup(path)

        # the file might have been moved so there is nothing left to be done
        if not path.exists():
            return

        logger.info('removing path %s', str(path))
        try:
            if path.is_dir():
                path.rmdir()
            else:
                path.unlink()
        except OSError as error:
            raise UpsetFsError(f'could not delete "{path}"') from error

    @staticmethod
    def ensure_file(path: pathlib.Path, template: Template,
            permissions: PermissionSet,
            mode: str = 'force', backup: bool = True) -> None:
        """Make sure a file exists.

        If the file does not exist it will be created by interpolating the
        template string. If the file exists and `force_template` is `True`
        (default) it will be replaced using the template string. If anything but
        a symlink exists it will be backed up (see `Fs.backup()`) depending on
        `backup`.

        Args:
            path: The path to ensure a file.
            template: A template to be used to fill the file with.
            permissions: The permissions of the file.
            mode: What to do if the file exists ['asis'|'force'|'update']?
                'as_is': will leave the file as is if it exists.
                'force': will re-write the file.
                'update': If the source is newer the target will be replaced
                    (default).
            backup: Create a backup (see `Fs.backup()`; default is `True`).

        Raises:
            UpsetFsError: If filesystem interaction fails.
        """
        logger.info('ensuring file "%s"', str(path))
        if path.is_dir():
            logger.warning('creating file instead of directory %s',
                    str(path))
        elif path.is_file():
            if mode == 'asis':
                logger.debug('target "%s" exists and mode "asis"', str(path))
                return
            if mode != 'force':
                try:
                    source_mtime: float = template.file.stat().st_mtime
                    target_mtime: float = path.stat().st_mtime
                except OSError as error:
                    raise UpsetFsError(
                            'could not get mtime') from error
                if target_mtime > source_mtime:
                    logger.debug('target "%s" newer than source', str(path))
                    return

        # remove or backup the file if it exists
        Fs.remove(path, backup)

        try:
            content: str = string.Template(
                template.file.read_text(encoding='utf-8')).safe_substitute(
                        template.substitutes)
        except OSError as error:
            raise UpsetFsError(
                    'could not open template "{template.file}"') from error

        logger.info('creating file: %s', str(path))
        try:
            path.write_text(content, encoding='utf-8')
        except OSError as error:
            raise UpsetFsError(f'could not create file "{path}"') from error
        Fs.ensure_perms(path, permissions)

    @staticmethod
    def ensure_link(path: pathlib.Path, target: pathlib.Path,
            backup: bool = True) -> None:
        """Make sure symlink exists.

        If the symlink does not exist it will be created. If anything but
        a symlink exists it will be backed up (see `Fs.backup()`) depending on
        `backup`.

        Args:
            path: The path to ensure a symlink exists.
            target: The target of the symlink.
            backup: Create a backup (see `Fs.backup()`; default is `True`).

        Raises:
            UpsetFsError: If filesystem interaction fails.
        """
        logger.info('ensuring symlink "%s" tp "%s"', str(path), str(target))
        if path.is_symlink():
            if path.resolve().samefile(target):
                logging.debug('symlink "%s" already present', str(path))
                return
            path.unlink()
        elif path.exists():
            Fs.remove(path, backup)

        logger.info('creating symlink "%s"', str(path))
        path.symlink_to(target)

    @staticmethod
    def ensure_dir(path: pathlib.Path, permissions: PermissionSet,
            backup: bool) -> None:
        """Make sure directory exists.

        If the directory does not exist it will be created. If anything but
        a symlink exists it will be backed up (see `Fs.backup()`) depending on
        `backup`.

        Args:
            path: The path to ensure a symlink exists.
            permissions: The permissions of the file.
            backup: Create a backup (see `Fs.backup()`; default is `True`).

        Raises:
            UpsetFsError: If filesystem interaction fails.
        """
        logger.info('ensuring directory "%s"', str(path))
        if path.is_dir():
            logging.debug('directory "%s" already present', str(path))
            Fs.ensure_perms(path, permissions)
            return

        Fs.remove(path, backup)

        logger.info('creating directory "%s"', str(path))
        try:
            path.mkdir()
        except OSError as error:
            raise UpsetFsError(
                    f'could not create directory "{path}"') from error

        Fs.ensure_perms(path, permissions)

    @staticmethod
    def ensure_perms(path: pathlib.Path, permissions: PermissionSet) -> None:
        """Ensure a file or directory has the given permissions.

        Args:
            path: The path to ensure a file.
            permissions: The permissions to apply

        Raises:
            UpsetFsError: If filesystem interaction fails.
        """
        current_mode = oct(stat.S_IMODE(path.lstat().st_mode))

        if path.is_symlink():
            logger.warning('cannot change permissions on symlink "%s"',
                    str(path))
            return

        logging.debug('current mode: %s; should be %s', str(current_mode),
                str(permissions.mode))

        try:
            if current_mode != oct(permissions.mode):
                logger.info('changing permissions of file "%s"', str(path))
                path.chmod(permissions.mode)
            if path.owner() != permissions.owner:
                if permissions.owner == '':
                    owner: int = -1
                else:
                    owner = pwd.getpwnam(permissions.owner).pw_uid
                logger.info('changing owner of file "%s"', str(path))
                os.chown(str(path), uid=owner, gid=-1, follow_symlinks=False)
            if path.group() != permissions.group:
                if permissions.group == '':
                    group: int = -1
                else:
                    group = grp.getgrnam(permissions.group).gr_gid
                logger.info('changing group of file "%s"', str(path))
                os.chown(str(path), uid=-1, gid=group, follow_symlinks=False)
        except OSError as error:
            raise UpsetFsError(
                    f'could not change permissions on "{path}"') from error

    @staticmethod
    def ensure_in_file(path: pathlib.Path, text: str, insert_at: str = r'\Z',
            backup = True) -> None:
        """Ensure a string occcurs in a file.

        Args:
            path: The path to ensure a file.
            text: The text that must occur in the file.
            insert_at: The position where the text must occur. Must be a valid
                regular expression. Default is to much the end of the file
                appending the text to the file.
            backup: Create a backup (see `Fs.backup()`; default is `True`).

        Raises:
            UpsetFsError: If filesystem interaction fails.
        """
        try:
            haystack: str = path.read_text(encoding='utf-8')
        except OSError as error:
            raise UpsetFsError(
                    f'could not read file "{path}"') from error

        logger.info('ensuring "%s" is in "%s"', text.split('\n')[0], str(path))

        if re.search(text, haystack):
            logger.debug('text is already in the file')
            return

        if backup:
            Fs.backup(path)

        logger.info('inserting "%s" into "%s"', text.split('\n')[0], str(path))
        haystack = re.sub(insert_at, text, haystack)

        try:
            path.write_text(haystack, encoding='utf-8')
        except OSError as error:
            raise UpsetFsError(
                    f'could not write file "{path}"') from error


class Plugin:
    """

    Attributes:
        _target: Variable that
    """

    def __init__(self) -> None:
        """Initialise and log it."""
        logger.info('loading %s', self.__class__.__name__)

    def run(self) -> None:
        """Entry point."""
        params = self.load_task()

    @staticmethod
    def load_task() -> dict[str, str]:
        """Load task.

        Returns:
            A.
        """
        logger.debug('task')
        return dict({'var1': 'var2'})

