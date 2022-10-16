"""Library providing basic functionality and a base class for plugins."""

import configparser
import logging
import pathlib

logger: logging.Logger = logging.getLogger()

class Fs:
    """Filesystem related functions."""

    @staticmethod
    def backup(path: pathlib.Path) -> None:
        """Backup a file by moving it to "FILENAME(.SUFFIX).bk".

        Args:
            path: The path to the file to backup.
        """
        try:
            if not path.is_file():
                logger.error('cannot backup file "%s"', str(path))
            path.replace(pathlib.Path(str(path) + '.bk'))
        except OSError as error:
            logger.error('could not backup "%s" (%s)', str(path), str(error))


    @staticmethod
    def ensure_file(path: pathlib.Path, mode: int, owner: str, group: str,
            template: str = '', substitutes: dict[str, str] = {},
            force_template: bool = False, backup: bool = True):
        """

        Args:
            path: The path to ensure a file.
            mode: The file mode (octal value).
            owner: The file owner (existence will not be checked / ensured).
            group: The group (existence will not be checked / ensured).
            template: A template to be used to fill the file.
            substitutes: Substitute occurences of the given variables by their
                values.
            force_templates: Apply template even if the file exists (overwrites
                the file).
            backup: Create a backup (see `Fs.backup()`).
        """

        template = Template(template).safe_substitute(substitutes)

        if path.exists():
            if not path.is_file() or (force_template and template != path.read_text()):
                self._remove(path, True)
                create = True
            else:
                create = False
                logging.debug(' - File {0} present'.format(str(path)))
        else:
            if path.is_symlink():
                self._remove(path, False)
            create = True
        if create:
            logger.info(' - Creating file: {0}'.format(str(path)))
            path.write_text(template)

        self._ensure_perms(path, mode, owner, group)

    def _ensure_link(self, path, target, backup, mode, owner, group):
        if path.is_symlink():
            if path.exists() and path.resolve().samefile(target):
                logging.debug(' - Symlink {0} present'.format(str(path)))
                create = False
            else:
                self._remove(path, False)
                create = True
        elif path.exists():
            self._remove(path, True)
            create = True
        else:
            create = True

        if create:
            logger.info(' - Creating symlink: {0}'.format(str(path)))
            path.symlink_to(target)

        self._ensure_perms(path, mode, owner, group)

    def _ensure_dir(self, path, backup, mode, owner, group):
        if path.exists():
            if not path.is_dir():
                self._remove(path, True)
                create = True
            else:
                create = False
                logging.debug(' - Directory {0} present'.format(str(path)))
        else:
            if path.is_symlink():
                self._remove(path, False)
            create = True

        if create:
            logger.info(' - Creating directory: {0}'.format(str(path)))
            path.mkdir()

        self._ensure_perms(path, mode, owner, group)

    def _ensure_perms(self, path, mode, owner, group):
        current_mode = oct(S_IMODE(path.lstat().st_mode))

        if not path.is_symlink():
            logging.debug(
                ' - File is: {0}; should be {1}'.format(current_mode, oct(mode)))
            if current_mode != oct(mode):
                logger.info(' - Updating permissions of file {0}'.format(str(path)))
                os.chmod(str(path), mode)#, follow_symlinks=False)
            if path.owner() != owner:
                owner = pwd.getpwnam(owner).pw_uid
                logger.info(' - Updating owner of file {0}'.format(str(path)))
                os.chown(str(path), uid=owner, gid=-1, follow_symlinks=False)
            if path.group() != group:
                group = grp.getgrnam(group).gr_gid
                logger.info(' - Updating group of file {0}'.format(str(path)))
                os.chown(str(path), uid=-1, gid=group, follow_symlinks=False)

    def _remove(self, path, backup):
        if path.exists() or path.is_symlink():
            if backup:
                path.rename(str(path) + '.bk')
            else:
                logger.info(' - Removing file {0}'.format(str(path)))
                path.unlink()

    def _is_user_path(self, path):
        return True if not re.search('\$USER', str(path)) is None else False

    def ensure(self, path='', type='', target='', template='', state='present',
        backup=True, mode=0o600, owner='$USER', group='$USER', users=[],
        force_template=False, substitutes={}):

        path = Path(path)
        target = Path(target)

        is_user_path = self._is_user_path(path)
        if is_user_path and len(users) == 0:
            raise ValueError('No users given, but variable $USER used.')
        elif len(users) == 0:
            users.append(owner)

        for user in users:
            pth = Path(re.sub('\$USER', user, str(path)))
            trgt = Path(re.sub('\$USER', user, str(target)))
            ownr = re.sub('\$USER', user, owner)
            grp = re.sub('\$USER', user, group)
            subs = {}
            subs = substitutes
            subs['USER'] = user

            logger.info(
                'Fs: Ensure {0} at {1} is {2}'.format(type, pth, state))

            if state == 'present':
                if type == 'file':
                    self._ensure_file(
                        pth, template, backup, mode, ownr, grp, force_template, subs)
                elif type == 'dir':
                    self._ensure_dir(pth, backup, mode, ownr, grp)
                elif type == 'symlink':
                    self._ensure_link(pth, trgt, backup, mode, ownr, grp)
                else:
                    raise ValueError('Invalid type')
            elif state == 'absent':
                self._remove(pth, backup)
            else:
                raise ValueError('Invalid state')

        return


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

