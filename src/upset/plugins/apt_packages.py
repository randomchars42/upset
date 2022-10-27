#!/usr/bin/python3
"""
Plugin to ensure users exist.

Can handle:
 - detection if installed packages
 - installation of deb-packages via apt
 - removal of deb-packages via apt

Examples::

    # Exemplary task description
    {
        "name": "ensure my packages",
        "plugin": "apt_packages",
        "variables": {
            "packages": [
                # describe a repository update
                {
                    "ensure": "update",
                },
                # describe an upgrade of all packges
                {
                    "ensure": "upgrade",
                },
                # describe packages that must be present
                {
                    "names": ["package1", "package2"],
                    "ensure": "present",
                },
                # describe packages that must not be present
                {
                    "names": ["package3", "package4"],
                    "ensure": "absent",
                },
                # describe cleaning of cached packages
                {
                    "ensure": "clean",
                },
                # describe autocleaning of cached packages
                {
                    "ensure": "autoclean",
                },
                # describe removing all packages that are not necessary
                # anymore
                {
                    "ensure": "autoremove",
                },
        },
    }
"""
import logging
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

class AptPackages(lib.Plugin):
    """Handle installation / removal of packages."""

    def run(self) -> None:
        """Do the main work."""
        for subtask in self.data['variables']['users']:
            if subtask['ensure'] == 'present':
                self.ensure_packages(subtask['names'])
            elif subtask['ensure'] == 'absent':
                self.ensure_packages_absent(subtask['names'])
            elif subtask['ensure'] == 'update':
                self.apt_do('update')
            elif subtask['ensure'] == 'upgrade':
                self.apt_do('upgrade')
            elif subtask['ensure'] == 'clean':
                self.apt_do('clean')
            elif subtask['ensure'] == 'autoclean':
                self.apt_do('autoclean')
            elif subtask['ensure'] == 'autoremove':
                self.apt_do('autoremove')
            else:
                raise lib.UpsetError(
                        f'no such subtask "{subtask["ensure"]}"')

    def package_installed(self, package: str) -> bool:
        """Test if the package exists on the system.

        Args:
            name: The packages's name.

        Returns:
            `True` if the package exists else `False`.
        """
        try:
            lib.Sys.run_command(lib.Sys.build_command(['dpkg', '-s', package]))
        except lib.UpsetSysError:
            return False
        return True

    def ensure_packages(self, packages: list[str]):
        """Ensure packages are present.

        Args:
            packages: The names of the packages that need to be present.
        """
        logger.info('ensuring packages "%s" are present', ', '.join(packages))

        package: str
        to_install: list[str] = []
        for package in packages:
            if self.package_installed(package):
                continue
            to_install.append(package)

        if len(to_install) == 0:
            return

        logger.info('installing packages "%s"', ', '.join(to_install))
        print('installing packages "%s"', ', '.join(to_install))
        #lib.Sys.run_command(lib.Sys.build_command(
        #    ['apt-get', 'install'] + to_install,
        #    sudo=True))

    def ensure_packages_absent(self, packages: list[str]) -> None:
        """Ensure packages are present.

        Args:
            packages: The names of the packages that need to be present.
        """
        logger.info('ensuring packages "%s" are absent', ', '.join(packages))

        package: str
        to_remove: list[str] = []
        for package in packages:
            if not self.package_installed(package):
                continue
            to_remove.append(package)

        if len(to_remove) == 0:
            return

        logger.info('removing packages "%s"', ', '.join(to_remove))
        print('removing packages "%s"', ', '.join(to_remove))
        print(lib.Sys.build_command(
            ['apt-get', 'remove'] + to_remove,
            sudo=True))
        lib.Sys.run_command(lib.Sys.build_command(
            ['sudo', 'apt-get', 'remove'] + to_remove,
            sudo=True))

    def apt_do(self, task: str) -> None:
        """Do some tasks that cannot be tested as states.

        Args:
            task: Apt command, one of ['update', 'upgrade', 'clean',
                'autoclean', 'autoremove'].
        """
        logger.info('Calling apt-get "%s"', task)

        lib.Sys.run_command(lib.Sys.build_command(
            ['sudo', 'apt-get', task], sudo=True))

if __name__ == '__main__':
    apt_packages: AptPackages = AptPackages()
    try:
        apt_packages.run()
    except lib.UpsetError as error:
        logger.error(error)
        sys.exit(1)
    except KeyError as error:
        logger.error(error)
        sys.exit(1)
