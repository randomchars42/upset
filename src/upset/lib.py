"""Library providing basic functionality and a base class for plugins."""

import base64
import dataclasses
import getpass
import grp
import json
import logging
import os
import pathlib
import pwd
import re
import shutil
import socket
import stat
import string
import subprocess
import sys

from typing import Any, Optional

logger: logging.Logger = logging.getLogger()
logger.addHandler(logging.NullHandler())

@dataclasses.dataclass
class Template():
    """Holds a template string and its variables.

    Attributes:
        string: The file with `$variables` to use as content.
        substitutes: A dictionary with the variable names as keys and
            their substitutes as values.
    """
    file: pathlib.Path
    substitutes: dict[str, str]

class UpsetError(Exception):
    """Custom exception."""

class UpsetSysError(UpsetError):
    """Error for Sys interactions."""

class UpsetFsError(UpsetError):
    """Error for Fs interactions."""

class UpsetHelperError(UpsetError):
    """Error for Helper interactions."""

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

        # the file might have been moved so there is nothing left to be
        # done
        if not path.exists():
            return

        logger.info('removing path %s', str(path))
        try:
            if path.is_symlink():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
            else:
                path.unlink()
        except OSError as error:
            raise UpsetFsError(f'could not delete "{path}"') from error

    @staticmethod
    def ensure_file(path: pathlib.Path, template: Template,
            permissions: str, mode: str = 'force', backup: bool = True) -> None:
        """Make sure a file exists.

        If the file does not exist it will be created by interpolating
        the template string. If the file exists and `force_template` is
        `True` (default) it will be replaced using the template string.
        If anything but a symlink exists it will be backed up (see
        `Fs.backup()`) depending on `backup`.

        Args:
            path: The path to ensure a file.
            template: A template to be used to fill the file with.
            permissions: The permissions of the file.
                (see `lib.Fs.ensure_perms()`).
            mode: What to do if the file exists
                ['asis'|'force'|'update']?
                'as_is': will leave the file as is if it exists.
                'force': will re-write the file.
                'update': If the source is newer the target will be
                    replaced (default).
            backup: Create a backup (see `Fs.backup()`; default is
                `True`).

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

        if len(template.substitutes) != 0:
            try:
                content: str = string.Template(
                    template.file.read_text(encoding='utf-8')).safe_substitute(
                            template.substitutes)
            except OSError as error:
                raise UpsetFsError(
                        f'could not open template "{template.file}"') from error

            logger.info('creating file: %s', str(path))
            try:
                path.write_text(content, encoding='utf-8')
            except OSError as error:
                raise UpsetFsError(f'could not create file "{path}"') from error
        else:
            logger.info('copying file "%s" to "%s"', str(template.file),
                str(path))
            shutil.copy(str(template.file), str(path))
        Fs.ensure_perms(path, permissions)

    @staticmethod
    def ensure_link(path: pathlib.Path, target: pathlib.Path,
            backup: bool = True) -> None:
        """Make sure symlink exists.

        If the symlink does not exist it will be created. If anything
        but a symlink exists it will be backed up (see `Fs.backup()`)
        depending on `backup`.

        Args:
            path: The path to ensure a symlink exists.
            target: The target of the symlink.
            backup: Create a backup (see `Fs.backup()`; default is
                `True`).

        Raises:
            UpsetFsError: If filesystem interaction fails.
        """
        logger.info('ensuring symlink "%s" to "%s"', str(path), str(target))
        if path.is_symlink():
            if (path.exists() and target.exists() and
                path.resolve().samefile(target)):
                logging.debug('symlink "%s" already present', str(path))
                return
            path.unlink()
        elif path.exists():
            Fs.remove(path, backup)

        logger.info('creating symlink "%s"', str(path))
        path.symlink_to(target)

    @staticmethod
    def ensure_dir(path: pathlib.Path, permissions: str,
            backup: bool) -> None:
        """Make sure directory exists.

        If the directory does not exist it will be created. If anything
        but a symlink exists it will be backed up (see `Fs.backup()`)
        depending on `backup`.

        Args:
            path: The path to ensure a symlink exists.
            permissions: The permissions of the file
                (see `lib.Fs.ensure_perms()`).
            backup: Create a backup (see `Fs.backup()`; default is
                `True`).

        Raises:
            UpsetFsError: If filesystem interaction fails.
        """
        logger.info('ensuring directory "%s"', str(path))

        if not path.is_symlink() and path.is_dir():
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
    def ensure_path(path: pathlib.Path, path_permissions: str,
            backup: bool) -> None:
        """Make sure directory exists.

        If the directory does not exist it will be created. If anything
        but a symlink exists it will be backed up (see `Fs.backup()`)
        depending on `backup`.

        Permissions: The permission string is split by "/". Each part is
        expected to be an interpretable permission string (see
        `lib.Fs.ensure_perms()`). The number of parts must match the
        number of directories in the path:

        E,g,:

        For a path `/home/USER/.config` The string could look like:
        - `"/-/-/-"` to leave everything as it was before or was
            created using the umask and root(!) as owner and group.
        - `"/-/-/."` leaves `home` and `USER` as before and sets
            `.config` to the same permissions as `USER`
        - `"/-/-/user,group,-"`: change user and group but leave mode as
            it is.
        - `"/-/-/user,group,700"`: being even more specific.

        Args:
            path: The path to ensure a symlink exists.
            path_permissions: The permissions of the file. See above
            backup: Create a backup (see `Fs.backup()`; default is
                `True`).

        Raises:
            UpsetFsError: If filesystem interaction fails.
        """
        logger.info('ensuring path "%s"', str(path))

        permissions: list[str] = path_permissions.split('/')

        if len(permissions) != len(path.parts):
            raise UpsetFsError(f'permissions "{path_permissions}" do not '
                    f'match path "{path}"')

        i: int = 1
        for part in path.parts:
            i += 1
            if part == '/':
                permissions.pop(0)
                continue
            logger.debug('ensuring part "%s" with permissions "%s"',
                    '/'.join(path.parts[1:i-1]), permissions[0])
            Fs.ensure_dir(pathlib.Path(f'/{"/".join(path.parts[1:i-1])}'),
                    permissions.pop(0), backup)

    @staticmethod
    def ensure_perms(path: pathlib.Path, permissions: str) -> None:
        """Ensure a file or directory has the given permissions.

        For ease of use permissions are indicated using a string::

            `"user1,group1,755"`

        Translates to: set `owner` to `"user1"`, `group` to `"group1"`
        and mode to `0755`.

        Each portion can be left as is by writing "-"::

            `"user1,-,-"`

        This will set only the owner while leaving group and mode as is.

        So, "-,-,-" leaves everything as it is. So does "-" (shorter
        for your convenience).

        "." is interpreted as: use the same permission as the parent
        directory (so it does only make sense on directories and can't
        be applied to root - but you wouldn't change root anyway, would
        you?): ".,group2,.", ..., ".,.,." (or short ".")

        Args:
            path: The path to ensure a file.
            permissions: The permissions to apply.

        Raises:
            UpsetFsError: If filesystem interaction fails.
        """

        if permissions in ('-', '-,-,-'):
            # leave everything as it is
            return

        if path.is_symlink():
            logger.warning('cannot change permissions on symlink "%s"',
                    str(path))
            return


        parent: pathlib.Path = path.resolve().parent
        if permissions == '.':
            owner: str = parent.owner()
            group: str = parent.group()
            # stat.S_IMODE will return a decimal representation of the
            # octal value, e.g. 493 for 0o755
            # we want a string that can be treated the same way as user
            # input that would be like "755"
            # so we use `oct()` which returns a string like:
            # oct(493) == "0o755"
            # and remove the "0o" part
            mode: str = oct(stat.S_IMODE(parent.lstat().st_mode))[2:]
        else:
            try:
                owner,group,mode = permissions.split(',')
                owner = owner if owner != '.' else parent.owner()
                group = group if group != '.' else parent.group()
                mode = mode if mode != '.' else oct(
                        stat.S_IMODE(parent.lstat().st_mode))[2:]
            except ValueError as error:
                raise UpsetFsError(
                        f'malformed permissions "{permissions}"') from error

        current_mode: str = oct(stat.S_IMODE(path.lstat().st_mode))[2:]

        logging.debug('current owner: %s; should be %s', path.owner(),
                owner)
        logging.debug('current group: %s; should be %s', path.group(),
                group)
        logging.debug('current mode: %s; should be %s', current_mode,
                mode)

        try:
            if mode not in (current_mode, '-'):
                logger.info('changing permissions of file "%s"', str(path))
                # interpret string as octal
                path.chmod(int(mode, 8))
            if owner not in (path.owner(), '-'):
                logger.info('changing owner of file "%s"', str(path))
                os.chown(str(path), uid=pwd.getpwnam(owner).pw_uid, gid=-1,
                        follow_symlinks=False)
            if group not in (path.group(), '-'):
                logger.info('changing group of file "%s"', str(path))
                os.chown(str(path), uid=-1, gid=grp.getgrnam(group).gr_gid,
                        follow_symlinks=False)
        except OSError as error:
            raise UpsetFsError(
                    f'could not change permissions on "{path}"') from error

    @staticmethod
    def ensure_in_file(path: pathlib.Path, text: str, insert_at: str = r'\Z',
                       needle: str = '', backup = True) -> None:
        """Ensure a string occcurs in a file.

        Args:
            path: The path to ensure a file.
            text: The text that must occur in the file.
            insert_at: The position where the text must occur. Must be
                a valid regular expression. Default is to much the end
                of the file appending the text to the file.
            needle: If the text is too complex search for needle as a
                surrogate.
            backup: Create a backup (see `Fs.backup()`; default is
                `True`).

        Raises:
            UpsetFsError: If filesystem interaction fails.
        """
        try:
            if not path.exists():
                path.touch()
            haystack: str = path.read_text(encoding='utf-8')
        except OSError as error:
            raise UpsetFsError(
                    f'could not read file "{path}"') from error

        logger.info('ensuring "%s" is in "%s"', text.split('\n')[0], str(path))

        if needle == '':
            needle = text

        if re.search(needle, haystack):
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

class Sys:
    """Provide interactions with the system."""

    @staticmethod
    def run_command(command_parts: list[str]) -> str:
        """Run a command as a subprocess.

        Args:
            command_parts: The command with parameters, each in its own
                string.

        Returns:
            Output of the command (without final `"\n"`).

        Raises:
            UpsetError: Raised if the remote command fails.
        """
        try:
            executable_cand: Optional[str] = shutil.which(command_parts[0])
            command_parts[0] = executable_cand if executable_cand else \
                    command_parts[0]
            result: subprocess.CompletedProcess = subprocess.run(
                    command_parts, check=True,
                    capture_output=True)
            return (result.stdout.decode().strip() +
                    result.stderr.decode().strip())
        except subprocess.CalledProcessError as error:
            raise UpsetSysError(
                    f'command {" ".join(command_parts)} returned with '
                    f'"{error.returncode}":\n'
                    f'{error.output.decode()}\n'
                    f'{error.stderr.decode()}'
                    ) from error

    @staticmethod
    def build_sudo_command(command_parts: list[str], password: str,
            user: str = '', host: str = '',
            ssh_key: pathlib.Path = pathlib.Path(),
            run_as: str = 'root') -> list[str]:
        """Prepare a command to be run with sudo non-interactively.

        Achieves this by making `sudo` read the password from `stdin`
        (`-S`) and without a prompt (`--prompt=`). The password is
        `echo`ed and piped into `sudo`s `stdin`.

        To avoid having to deal with escaping issues the sequence
        `echo "{password}" | sudo -S --prompt= -- {command}` is encoded
        as `base64` (as suggested by "ThoriumBR" on
        <https://serverfault.com/questions/625641>).

        At the target the encoded sequence gets decoded by piping it to
        `base64 -d` and evaluating the output in the `$SHELL`.

        Beware: The command parts are simply joined with
        `" ".join(command)`.
        The behaviour might differ from
        `subprocess.check_output(command)`!

        Args:
            command_parts: The command to run with its parameters,
                each in its own string.
            password: The password to use with `sudo`.
            user: The user to log in with (see `Sys.build_command()`
                for default behaviour).
            host: The host to execute the task on (see
                `Sys.build_command()` for default behaviour).
            ssh_key: The ssh key or identity to use.
            run_as: Run the task as root (sudo) or as a different user
                without elevated privileges.

        Returns:
            A command that can be passed to a shell via
            `Sys.run_command()`.
        """
        command: str = ' '.join(command_parts)
        if run_as == 'root':
            run_as = ''
        else:
            run_as = f'-u {run_as}'
        # base64.b64encode() needs a byte-like argument so the string
        # is first "encoded"
        encoded_command: bytes = base64.b64encode(
                f'echo "{password}" | sudo {run_as} -S --prompt= -- '
                    f'{command}\n'.encode())
        # the result is a bytestream so it is "decoded" to a string
        # but it is still base64-gibberish
        return Sys.build_command(
                [f'echo {encoded_command.decode()} | base64 -d | '
                    '$SHELL'],
                user, host, ssh_key)


    @staticmethod
    def build_command(command_parts: list[str], user: str = '',
            host: str = '', ssh_key: pathlib.Path = pathlib.Path(),
            sudo: bool = False) -> list[str]:
        """Run a command on a remote host.

        Args:
            command_parts: The command with parameters to run on `host`,
                each as its own string.
            user: The user to log in with (see `Sys.build_command()`
                for default behaviour).
            host: The host to execute the task on (see
                `Sys.build_command()` for default behaviour).
            ssh_key: The ssh key or identity to use.
            sudo: Prepend sudo. For commands as current user on current
                machine only.
        """
        if user == '':
            user = getpass.getuser()
        if host == '':
            host = socket.gethostname()

        if host == socket.gethostname() and user == getpass.getuser():
            if sudo:
                return ['sudo', '--'] + command_parts
            return ['bash', '-c', ' '.join(command_parts)]

        return ['ssh', '-i', str(ssh_key), f'{user}@{host}'] + command_parts

    @staticmethod
    def build_scp_command(local_path: pathlib.Path, remote_path: pathlib.Path,
            direction: str = 'to', user: str = '', host: str = '',
            ssh_key: pathlib.Path = pathlib.Path()) -> list[str]:
        """Build a command to copy files (from / to a remote machine).

        Though it can be used to move files locally this function is
        meant to copy files between hosts using scp. The ability to
        move files locally is used for debugging.

        Args:
            local_path: Path on the local machine.
            remote_path: Path on the remote machine.
            direction: Copy 'to' remote or 'from' remote.
            user: The user to log in with (see `Sys.build_command()`
                for default behaviour).
            host: The host to execute the task on (see
                `Sys.build_command()` for default behaviour).
            ssh_key: The ssh key or identity to use.
        """
        direction = direction.lower()

        if direction not in ['to', 'from']:
            raise UpsetSysError(f'not a valid option "{direction}"')

        if user == '':
            user = getpass.getuser()
        if host == '':
            host = socket.gethostname()

        local: str = str(local_path)
        remote: str = str(remote_path)

        if host == socket.gethostname() and user == getpass.getuser():
            # use this for debugging
            copy: list[str] = ['cp']
        else:
            copy = ['scp', '-i', str(ssh_key)]
            remote = f'{user}@{host}:/{remote}'

        if direction == 'to':
            source: str = local
            destination: str = remote
        else:
            source = remote
            destination = local

        return copy + ['-p', source, destination]

    @staticmethod
    def make_temporary_directory(user: str = '',
            host: str = '',
            ssh_key: pathlib.Path = pathlib.Path()) -> pathlib.Path:
        """Create a temporary directory for `user` on `host`.

        Args:
            user: The user to log in with (see `Sys.build_command()`
                for default behaviour).
            host: The host to execute the task on (see
                `Sys.build_command()` for default behaviour).
            ssh_key: The ssh key or identity to use.

        Returns:
            The path of the temporary directory.
        """
        try:
            tmp_dir: pathlib.Path = pathlib.Path(Sys.run_command(
                Sys.build_command(['mktemp', '-d'], user, host, ssh_key)))
            Sys.run_command(Sys.build_command(['mkdir', f'{tmp_dir}/upset'],
                user, host, ssh_key))
            return tmp_dir# / 'upset'
        except UpsetError as error:
            raise UpsetError(
                    'could not create temporary directory') from error

    @staticmethod
    def remove_temporary_directory(directory: pathlib.Path, password: str = '',
            user: str = '', host: str = '',
            ssh_key: pathlib.Path = pathlib.Path()) -> None:
        """Remove the temporary directory for `user` on `host`.

        Args:
            directory: The path to the temporary directory.
            password: The sudo password. This is required because the
                plugins are run as root and the remaining pyc-files
                can only be deleted using sudo.
            user: The user to log in with (see `Sys.build_command()`
                for default behaviour).
            host: The host to execute the task on (see
                `Sys.build_command()` for default behaviour).
            ssh_key: The ssh key or identity to use.
        """
        try:
            if directory.parts[1] == 'tmp':
                # make sure this is only called on /tmp/*
                Sys.run_command(
                    Sys.build_sudo_command(['rm', '-r', str(directory)],
                        password, user, host, ssh_key))
            else:
                Sys.run_command(
                    Sys.build_command(['rm', '-r', str(directory)], user,
                        host, ssh_key))
        except UpsetError as error:
            raise UpsetError(
                    'could not remove temporary directory') from error

    @staticmethod
    def ensure_ssh_key(user: str, host: str, key_file: pathlib.Path,
            authorized_keys_directory: pathlib.Path = pathlib.Path('~/.ssh/')):
        """Ensure the indicated ssh key is present.

        If it is not present one will be created and the pub key sent to
        the target machine and added to authorized_keys in the given
        directory.

        Args:
            user: The user to use the ssh key for.
            host: The host to use the ssh key on.
            key_file: The key file.
            authorized_keys_directory: The directory where
                `authorized_keys` normally reside (default: `~/.ssh/`).
                This can be changed for unittesting.
        """
        logger.info('ensure "%s" has ssh key for "%s" ("%s")', user, host,
                str(key_file))

        if key_file.is_file():
            return

        logger.info('creating ssh key for "%s" on "%s"', user, host)

        Sys.run_command(Sys.build_command([
            'ssh-keygen', '-q', '-N', '""', '-f', str(key_file)]))

        authorized_keys: pathlib.Path = authorized_keys_directory / \
                'authorized_keys'

        pub_key_file: pathlib.Path = pathlib.Path(f'{key_file}.pub')

        print(f'Please enter the password for {user}@{host} to make key files' \
                'work')

        proc: subprocess.Popen
        with subprocess.Popen(
                [f'{shutil.which("ssh")}', f'{user}@{host}',
                    'umask', '077', '&&',
                    'mkdir', '-p', str(authorized_keys_directory), '&&',
                    'chmod', '700', str(authorized_keys_directory), '&&',
                    'touch', str(authorized_keys), '&&',
                    'chmod', '600', str(authorized_keys), '&&',
                    f'{{ [ -z `tail -1c {authorized_keys} 2>/dev/null` ] || ' \
                            f'echo >> "{authorized_keys}" || exit 1; }}', '&&',
                    'echo', f'"{pub_key_file.read_text(encoding="utf-8")}"',
                    '>>', str(authorized_keys)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE) as proc:
            proc.wait()
            if proc.stdout:
                logger.debug(proc.stdout.read())
            if proc.stderr:
                logger.debug(proc.stderr.read())

    @staticmethod
    def ensure_ssh_key_absent(user: str, host: str, key_file: pathlib.Path,
            authorized_keys_directory: pathlib.Path = pathlib.Path('~/.ssh/'),
            remove_remote_only: bool =  False):
        """Ensure there is no ssh key for user on host.

        Args:
            user: The user to use the ssh key for.
            host: The host to use the ssh key on.
            key_file: The key file.
            authorized_keys_directory: The directory where
                `authorized_keys` normally reside (default: `~/.ssh/`).
                This can be changed for unittesting.
            remove_remote_only: Only remove key from authorized keys on
                host but keep the key file locally. Use if the same file
                is used for access on several machines.
        """
        logger.info('ensure ssh key "%s" is absent', str(key_file))

        if not key_file.is_file():
            return

        logger.info('removing ssh key for "%s" on "%s"', user, host)

        key_file_pub: pathlib.Path = pathlib.Path(str(key_file) + '.pub')
        key: str = key_file_pub.read_text(encoding='utf-8')

        key = re.sub(r'([]\/$*.^|[])', r'\\\1', key)
        key = key.split(' ')[1]

        Sys.run_command(Sys.build_command([
            'sed', f'\'/{user}@{host}/ D\'', '-i~',
            f'{authorized_keys_directory}/authorized_keys'],
            user=user, host=host))

        if not remove_remote_only:
            key_file.unlink()
            key_file_pub.unlink()

class Helper:
    """Provide some functions."""

    @staticmethod
    def create_unique_file_name(file: pathlib.Path) -> str:
        """Create a more unique filename.

        Args:
            file: The file to create a new name for.

        Returns:
        The new name.
        """
        return '___'.join(file.resolve(strict=False).parts[1:])

    @staticmethod
    def localise_plugin(name: str, paths: list[pathlib.Path]) -> pathlib.Path:
        """Localise the plugin.

        Args:
            name: The name of the plugin.
            paths: List of paths to search for the plugin.

        Returns:
        Path to the plugin.

        Raises:
            UpserHelperError: Raised if the plugin can't be found.
        """
        for path in paths:
            plugin_path: pathlib.Path = path / f'{name}.py'
            if plugin_path.exists():
                return plugin_path
        raise UpsetHelperError(f'could not locate plugin "{name}"')

    @staticmethod
    def encode_data(data: Any) -> str:
        """Encode data passed as JSON object to a base64 string.

        Args:
            data: Data to encode, must be a valid JSON object.

        Returns:
            Encoded data.
        """
        try:
            return base64.b64encode(json.dumps(data).encode()).decode()
        except (TypeError, RecursionError, ValueError) as error:
            raise UpsetHelperError(
                    'could not dump and encode data') from error

    @staticmethod
    def decode_data(data: str) -> Any:
        """Decode data passed as a base64 string to a JSON object.

        Args:
            data: Data to decode, must be a valid string of a JSON
                object encoded as base64.

        Returns:
            Decoded JSON object.
        """
        try:
            return json.loads(base64.b64decode(data).decode())
        except (TypeError, RecursionError, ValueError) as error:
            raise UpsetHelperError(
                    'could not decode and load data') from error

class Plugin:
    """Baseclass for plugins providing data decoded from the call.

    Attributes:
        data: The data that was given by the main process.

    Examples:
        You can either use this class like this::

            import lib

            class MyPlugin(lib.Plugin):
                def run(self) -> None:
                    # the data defined in the plugin is stored under
                    # `self.data['variables']`
                    print(self.data['variables']['var_a'])
                    # files are stored under:
                    # `self.data['files']`
                    for label, file in self.data['files']:
                        print(f'File with label "{label}" has name'
                            f'"{file}" on the target machine')
                    # the current value  of the special variables
                    # defined by `Task.foreach_variable`
                    # are stored in `Task.for`, e.g.,
                    # `Task.foreach = [
                    #   {'user': 'user1', 'group': 'group1'},
                    #   {'user': 'user2', 'group': 'group2'}]`
                    print(
                        f'doing this for: "{self.data['for']['user']}"')
                    # prints "user1" when the script is first executed
                    # and "user2" on the second run

        Or you can dispense with classes altogether::

            import lib

            data = lib.Plugin.get_data()
            print(data['variables']['var_a'])
            for label, file in data['files']:
                print(f'File with label "{label}" has name "{file}" on'
                        f'the target machine')
            print(f'doing this for user: "{data['user']}"')
    """

    def __init__(self) -> None:
        """Initialise and log it."""
        logger.info('loading %s', self.__class__.__name__)
        self.data = Plugin.get_data()

    def run(self) -> None:
        """Entry point."""

    @staticmethod
    def get_data() -> dict[str, Any]:
        """Get data for the task.

        Returns:
            A dictionary containing the data.
        """
        return Helper.decode_data(sys.argv[1])

