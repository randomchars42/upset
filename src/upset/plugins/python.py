#!/usr/bin/python3
"""
Setup a python toolchain.

Can handle:
 - ensuring pyenv is installed and configured
 - deletion of pyenv
 - ensuring pipenv is installed and configured
 - deletion of pipenv
 - ensuring pipx is installed and configured
 - deletion of pipx
 - ensuring packages are installed in python
 - ensuring packages are installed via pipx

Examples::

    # Exemplary task description
    {
        "name": "ensure my python",
        "plugin": "python",
        "variables": {
            "python": [
                # ensure pyenv is installed
                {
                    "path": "~/.pyenv",
                    "ensure": "pyenv",
                    "bashrc": "~/.bashrc.d/pyenv",
                },
                # ensure pyenv is absent
                {
                    "path": "~/.pyenv",
                    "ensure": "pyenv_absent"
                },
                # ensure a python version is installed
                {
                    "version": "3.11",
                    "ensure": "python",
                    "pyenv": "~/.pyenv"
                },
                # ensure a python version is absent
                {
                    "version": "3.11",
                    "ensure": "python_absent",
                    "pyenv": "~/.pyenv"
                },
                # ensure pip is installed for python version X
                {
                    "python": "3.11",
                    "ensure": "pip",
                    "pyenv": "~/.pyenv"
                },
                # ensure pipx is installed
                {
                    "path": "~/.pipx",
                    "ensure": "pipx",
                    "bashrc": "~/.bashrc.d/pipx",
                    "python": "3.11",
                    "pyenv": "~/.pyenv"
                },
                # ensure packages are installed via pip
                {
                    "names": ["name", "name2"],
                    "ensure": "packages",
                    "python": "3.11",
                    "pyenv": "~/.pyenv",
                    "manager": "pip"
                },
                # ensure packages are absent via pip
                {
                    "names": ["name", "name2"],
                    "ensure": "packages_absent",
                    "python": "3.11",
                    "pyenv": "~/.pyenv",
                    "manager": "pip"
                },
                # ensure packages are installed via pipx
                {
                    "names": ["name", "name2"],
                    "ensure": "packages",
                    "python": "3.11",
                    "pyenv": "~/.pyenv",
                    "manager": "pipx"
                },
                # ensure packages are absent via pipx
                {
                    "names": ["name", "name2"],
                    "ensure": "packages_absent",
                    "python": "3.11",
                    "pyenv": "~/.pyenv",
                    "manager": "pipx"
                }
            ]
        }
    }
"""
import logging
import pathlib
import sys

from upset import lib

# create console handler and set level to debug
logging_handler: logging.StreamHandler = logging.StreamHandler()
logging_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(levelname)s %(name)s %(message)s')
logging_handler.setFormatter(formatter)
root_logger: logging.Logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(logging_handler)
logger: logging.Logger = logging.getLogger(__name__)

class Python(lib.Plugin):
    """Handle creation / deletion of users."""

    def run(self) -> None:
        """Do the main work."""
        for subtask in self.data['variables']['python']:
            if subtask['ensure'] == 'pyenv':
                self.ensure_pyenv(
                        pathlib.Path(subtask['path']),
                        pathlib.Path(subtask.get('bashrc',
                                                 '~/.bashrc.d/pyenv')))
            elif subtask['ensure'] == 'pyenv_absent':
                self.ensure_pyenv_absent(subtask['path'])
            elif subtask['ensure'] == 'python':
                self.ensure_python(subtask['version'],
                                   subtask.get('pyenv', '~/.pyenv'))
            elif subtask['ensure'] == 'python_absent':
                self.ensure_python_absent(subtask['python'],
                                   subtask.get('pyenv', '~/.pyenv'))
            elif subtask['ensure'] == 'pip':
                self.ensure_pip(subtask.get('python', 'system'),
                                   subtask.get('pyenv', '~/.pyenv'))
            elif subtask['ensure'] == 'pipx':
                self.ensure_pipx(
                    pathlib.Path(subtask['path']),
                    pathlib.Path(subtask.get('bashrc', '~/.bashrc.d/pipx')),
                    subtask.get('python', 'system'),
                    subtask.get('pyenv', '~/.pyenv'))
            elif subtask['ensure'] == 'pipx_absent':
                self.ensure_pipx_absent(
                    pathlib.Path(subtask['path']),
                    subtask.get('python', 'system'),
                    subtask.get('pyenv', '~/.pyenv'))
            elif subtask['ensure'] == 'packages':
                self.ensure_packages(
                    subtask['manager'],
                    subtask['names'],
                    subtask.get('python', 'system'),
                    subtask.get('pyenv', '~/.pyenv'),
                    subtask.get('pipx', '~/.pipx'))
            elif subtask['ensure'] == 'packages_absent':
                self.ensure_packages_absent(
                    subtask['manager'],
                    subtask['names'],
                    subtask.get('python', 'system'),
                    subtask.get('pyenv', '~/.pyenv'),
                    subtask.get('pipx', '~/.pipx'))
            else:
                raise lib.UpsetError(
                        f'no such subtask "{subtask["ensure"]}"')

    def pyenv_exists(self, path: pathlib.Path) -> bool:
        """Test if pyenv exists on the given path.

        Args:
            path: The path to search.

        Returns:
            `True` if pyenv exists else `False`.
        """
        return path.exists()

    def ensure_pyenv(self, path: pathlib.Path,
                     path_bashrc: pathlib.Path) -> None:
        """Ensure pyenv is installed.

        Args:
            path: The path where pyenv should exist.
            path_bashrc: The path to the bashrc to modify.
        """
        logger.info('ensuring pyenv exists under "%s"', str(path))

        output: str = ''
        if not self.pyenv_exists(path):
            # install
            logger.debug('installing pyenv under "%s"', str(path))
            output = lib.Sys.run_command(lib.Sys.build_command([
                'git', 'clone', 'https://github.com/pyenv/pyenv.git',
                str(path)]))
            if output != '':
                print(output)
            output = lib.Sys.run_command(lib.Sys.build_command([
                'chown', '-R',
                f'{path.parent.owner()}:{path.parent.group()}', str(path)]))
            if output != '':
                print(output)
        else:
            logger.info('pyenv already exists under "%s"', str(path))

        # make pyenv available:
        # export PYENV_ROOT="PATH"
        # command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"
        # eval "$(pyenv init -)"

        lib.Fs.ensure_in_file(
                path_bashrc,
                f'export PYENV_ROOT="{path}"',
                r'\Z',
                '',
                False)

        lib.Fs.ensure_in_file(
                path_bashrc,
                'command -v pyenv >/dev/null || '
                    'export PATH="$PYENV_ROOT/bin:$PATH"',
                r'\Z',
                'command -v pyenv',
                False)

        lib.Fs.ensure_in_file(
                path_bashrc,
                'eval "$(pyenv init -)"',
                r'\Z',
                'pyenv init',
                False)

    def ensure_pyenv_absent(self, path: pathlib.Path) -> None:
        """Ensure pyenv is absent from path.

        Args:
            path: The path where pyenv should exist.
        """
        logger.info('ensuring pyenv does not exists under "%s"', str(path))

        if not self.pyenv_exists(path):
            logger.debug('pyenv does not exist under "%s"', str(path))
            return

        logger.info('removing pyenv from "%s"', str(path))

        # grabbag of severe mistakes
        if str(path) in ['/', '/boot', '/home']:
            raise lib.UpsetError(f'pyenv should not befound under "{path}"')
        output: str = lib.Sys.run_command(lib.Sys.build_command([
            'rm', '-r', str(path)]))
        if output != '':
            print(output)

    def pyenv_do(self, do: str, version: str, pyenv: str, pipx: str) -> str:
        """Do something via pyenv exec.

        Args:
            do: What to do.
            version: The python version to check.
            pyenv: Path to the python executable.
            pipx: PIPX_HOME.
        """
        if version != '':
            version = f'PYENV_VERSION={version} '
        if pipx != '':
            pipx = f'PIPX_HOME=\"{pipx}\" '
        return lib.Sys.run_command(lib.Sys.build_command([
            'bash', '-c',
            f'"PYENV_ROOT=\"{pyenv}\" {version}{pipx}'
                f'\"{pyenv}/bin/pyenv\" {do}"']))

    def python_exists(self, version: str, pyenv: str) -> bool:
        """Test if python version exists.

        Args:
            version: The version to test.
            pyenv: Path to the python executable.

        Returns:
            `True` if the version exists else `False`.
        """
        installed: list[str] = self.pyenv_do(
            'versions', '', pyenv, '').split('\n')
        for installed_version in installed:
            installed_version = installed_version[2:].split(' ')[0]
            print(installed_version)
            if version == installed_version:
                return True
        return False

    def ensure_python(self, version: str, pyenv: str) -> None:
        """Ensure the required version of python exists.

        Args:
            version: The version that is required.
            pyenv: Path to the python executable.
        """
        logger.info('ensuring python version "%s" exists', version)

        if self.python_exists(version, pyenv):
            logger.debug('python version "%s" already exists', version)
            return

        logger.info('installing python version "%s"', version)
        output: str = self.pyenv_do(f'install {version}', version, pyenv, '')
        if output != '':
            print(output)

    def ensure_python_absent(self, version: str, pyenv: str) -> None:
        """Ensure the version of python does not exists.

        Args:
            version: The version that is required to be absent.
            pyenv: Path to the python executable.
        """
        logger.info('ensuring python version "%s" does not exist', version)

        if not self.python_exists(version, pyenv):
            logger.debug('python version "%s" does not exist', version)
            return

        logger.info('removing python version "%s"', version)

        output: str = self.pyenv_do(f'uninstall {version}', version, pyenv, '')
        if output != '':
            print(output)

    def pipx_package_exists(self, name: str, version: str, pyenv: str,
            pipx: str) -> bool:
        """Test if a package was installed with pipx.

        Args:
            name: The package to check.
            version: The python version to check.
            pyenv: Path to the python executable.
            pipx: PIPX_HOME.

        Returns:
            `True` if package is installed with pipx under version
            else `False`.
        """
        installed: str = self.pyenv_do('exec pipx list --short', version,
            pyenv, pipx)
        return name in installed.split('\n')

    def pip_package_exists(self, name: str, version: str, pyenv: str) -> bool:
        """Test if a package was installed for the given python version.

        Args:
            name: The package to check.
            version: The python version to check.
            pyenv: Path to the python executable.

        Returns:
            `True` if package is installed under the python version
            else `False`.
        """
        try:
            self.pyenv_do(f'exec python -c \"import {name}\" 2>/dev/null',
                version, pyenv, '')
        except lib.UpsetError:
            return False
        return True

    def ensure_pip(self, version: str, pyenv: str) -> None:
        """Ensure pip is installed.

        Args:
            version: The python version the pipx package should run
                under.
            pyenv: Path to the python executable.
        """
        logger.info('ensuring pip exists under "%s"', version)

        if self.pip_package_exists('pip', version, pyenv):
            logger.info('pip already exists under "%s"', version)
        logger.debug('installing pip under "%s"', version)
        self.pyenv_do('exec python -m ensurepip --upgrade',
            version, pyenv, '')

    def package_do(self, packagemanager: str, name: str, action: str,
                   version: str, pyenv: str, pipx: str) -> None:
        """Ensure pip is installed.

        Args:
            packagemanager: The packagemanager (pip, pipx, pipenv).
            name: The name of the package.
            action: The action (install, remove)
            version: The python version the pipx package should run
                under.
            pyenv: Path to the python executable.
            pipx: PIPX_HOME.
        """
        self.pyenv_do(f'exec python -m {packagemanager} {action} {name}',
            version, pyenv, pipx)

    def ensure_pipx(self, path: pathlib.Path,
                    path_bashrc: pathlib.Path, version: str,
                    pyenv: str) -> None:
        """Ensure pipx is installed.

        Args:
            path: The path where pipx packages are installed to
                (PIPX_HOME).
            path_bashrc: The path to the bashrc to modify.
            version: The python version the pipx package should run
                under.
            pyenv: Path to the python executable.
        """
        logger.info('ensuring pipx exists under "%s"', version)

        if not self.pip_package_exists('pipx', version, pyenv):
            # install
            logger.debug('installing pipx under "%s"', str(path))
            self.package_do('pip', 'pipx', 'install', version, pyenv, str(path))
            self.pyenv_do('exec python -m pipx ensurepath', version, pyenv,
                str(path))
        else:
            logger.info('pipx already exists under "%s"', str(path))

        # set pipx home
        # export PIPX_HOME="PATH"

        lib.Fs.ensure_in_file(
                path_bashrc,
                f'export PIPX_HOME="{path}"',
                r'\Z',
                '',
                False)

    def ensure_pipx_absent(self, path: pathlib.Path, version: str,
            pyenv: str) -> None:
        """Ensure pipx is absent from python.

        Args:
            path: The path where pipx packages are installed to
                (PIPX_HOME).
            version: The python version pipx should be absent from.
            pyenv: Path to the python executable.
        """
        logger.info('ensuring pipx does not exists under "%s"', version)

        if not self.pip_package_exists('pipx', version, pyenv):
            logger.debug('pipx does not exist under "%s"', version)
            return

        logger.info('removing pipx from "%s"', version)
        self.package_do('pip', 'pipx', 'uninstall', version, pyenv, str(path))

    def ensure_packages(self, packagemanager: str, names: list[str],
                        version: str, pyenv: str, pipx: str) -> None:
        """Ensure package is installed.

        Args:
            packagemanager: The packagemanager (pip, pipx, pipenv).
            names: The name of the packages.
            version: The python version the package should run under.
            pyenv: Path to the python executable.
            pipx: PIPX_HOME.
        """
        logger.info('ensuring %s packages "%s" exist under "%s"',
            packagemanager, ', '.join(names), version)

        to_install: list[str] = []

        for name in names:
            if packagemanager == 'pip' and self.pip_package_exists(
                    name, version, pyenv):
                logger.info('"%s" (%s) already exists under "%s"',
                    packagemanager, name, version)
                continue
            elif packagemanager == 'pipx' and self.pipx_package_exists(
                    name, version, pyenv, pipx):
                logger.info('"%s" (%s) already exists under "%s"',
                    packagemanager, name, version)
                continue
            elif packagemanager not in ('pip', 'pipx'):
                raise lib.UpsetError(
                    f'unknown packagemanager "{packagemanager}"')
            to_install.append(name)

        logger.debug('installing %s packages "%s" under "%s"',
            packagemanager, ', '.join(to_install), version)
        for name in to_install:
            self.package_do(packagemanager, name, 'install', version, pyenv,
                pipx)

    def ensure_packages_absent(self, packagemanager: str, names: list[str],
        version: str, pyenv: str, pipx: str) -> None:
        """Ensure package is absent from python.

        Args:
            packagemanager: The packagemanager (pip, pipx, pipenv).
            names: The name of the packages.
            version: The python version the package should run under.
            pyenv: Path to the python executable.
            pipx: PIPX_HOME.
        """
        logger.info('ensuring %s packages "%s" do not exist under "%s"',
            packagemanager, ', '.join(names), version)

        to_remove: list[str] = []

        for name in names:
            if packagemanager == 'pip' and not self.pip_package_exists(
                    name, version, pyenv):
                logger.info('"%s" (%s) already does not exist under "%s"',
                    packagemanager, name, version)
                continue
            elif packagemanager == 'pipx' and not self.pipx_package_exists(
                    name, version, pyenv, pipx):
                logger.info('"%s" (%s) already does not exist under "%s"',
                    packagemanager, name, version)
                continue
            elif packagemanager not in ('pip', 'pipx'):
                raise lib.UpsetError(
                    f'unknown packagemanager "{packagemanager}"')
            to_remove.append(name)

        logger.debug('removing %s packages "%s" from "%s"',
            packagemanager, ', '.join(to_remove), version)
        for name in to_remove:
            self.package_do(packagemanager, name, 'uninstall', version, pyenv,
                pipx)


if __name__ == '__main__':
    python: Python = Python()
    try:
        python.run()
    except lib.UpsetError as error:
        logger.error(error)
        sys.exit(1)
    except KeyError as error:
        logger.error(error)
        sys.exit(1)
