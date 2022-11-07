#!/usr/bin/python3
"""
Plugin to ensure a dnf package is installed.

Can handle:
 - detection if packages are installed
 - installation of rpm-packages via dnf
 - removal of rpm-packages via dnf

Examples::

    # Exemplary task description
    {
        "name": "ensure my packages",
        "plugin": "dnf_packages",
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
                # describe groups of packages that must be present
                {
                    "names": ["package1", "package2"],
                    "ensure": "groups_present",
                },
                # describe groups of packages that must not be present
                {
                    "names": ["package3", "package4"],
                    "ensure": "groups_absent",
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

class DnfPackages(lib.Plugin):
    """Handle installation / removal of packages."""

    def run(self) -> None:
        """Do the main work."""
        self.installed_groups: list[str] = []

        for subtask in self.data['variables']['packages']:
            if subtask['ensure'] == 'present':
                self.ensure_packages(subtask['names'])
            elif subtask['ensure'] == 'absent':
                self.ensure_packages_absent(subtask['names'])
            elif subtask['ensure'] == 'groups_present':
                self.ensure_groups(subtask['names'])
            elif subtask['ensure'] == 'groups_absent':
                self.ensure_groups_absent(subtask['names'])
            elif subtask['ensure'] == 'update':
                self.dnf_do('check-update')
            elif subtask['ensure'] == 'upgrade':
                self.dnf_do('upgrade')
            elif subtask['ensure'] == 'clean':
                self.dnf_do('clean all')
            elif subtask['ensure'] == 'autoremove':
                self.dnf_do('autoremove')
            else:
                raise lib.UpsetError(
                        f'no such subtask "{subtask["ensure"]}"')

    def package_installed(self, package: str) -> bool:
        """Test if the package exists on the system.

        Args:
            package: The packages's name.

        Returns:
            `True` if the package exists else `False`.
        """
        try:
            lib.Sys.run_command(lib.Sys.build_command(['rpm', '-q', package]))
        except lib.UpsetSysError:
            return False
        return True

    def group_installed(self, group: str) -> bool:
        """Test if the package exists on the system.

        Args:
            group: The group's name.

        Returns:
            `True` if the package exists else `False`.
        """
        if len(self.installed_groups) == 0:
            installed: str = lib.Sys.run_command(lib.Sys.build_command([
                'dnf', 'group', 'list', 'installed']))
            self.installed_groups = [
                    item.strip() for item in installed.split('\n')]
        return group in self.installed_groups

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
        lib.Sys.run_command(lib.Sys.build_command(
            ['dnf', '-q', '-y', 'install'] + to_install,
            sudo=True))

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
        lib.Sys.run_command(lib.Sys.build_command(
            ['dnf', '-q', '-y', 'remove'] + to_remove,
            sudo=True))

    def ensure_groups(self, groups: list[str]):
        """Ensure package groups are present.

        Args:
            groups: The names of the groups that need to be present.
        """
        logger.info('ensuring groups "%s" are present', ', '.join(groups))

        group: str
        to_install: list[str] = []
        for group in groups:
            if self.group_installed(group):
                continue
            to_install.append(group)

        if len(to_install) == 0:
            return

        logger.info('installing groups "%s"', ', '.join(to_install))
        lib.Sys.run_command(lib.Sys.build_command(
            ['dnf', '-q', '-y', 'group', 'install'] + to_install,
            sudo=True))

    def ensure_groups_absent(self, groups: list[str]) -> None:
        """Ensure package groups are present.

        Args:
            packages: The names of the groups that need to be present.
        """
        logger.info('ensuring groups "%s" are absent', ', '.join(groups))

        group: str
        to_remove: list[str] = []
        for group in groups:
            if not self.package_installed(group):
                continue
            to_remove.append(group)

        if len(to_remove) == 0:
            return

        logger.info('removing groups "%s"', ', '.join(to_remove))
        lib.Sys.run_command(lib.Sys.build_command(
            ['dnf', '-q', '-y', 'group', 'remove'] + to_remove,
            sudo=True))

    def dnf_do(self, task: str) -> None:
        """Do some tasks that cannot be tested as states.

        Args:
            task: Dnf command, one of ['update', 'upgrade', 'clean',
                'autoremove'].
        """
        logger.info('Calling dnf "%s"', task)

        lib.Sys.run_command(lib.Sys.build_command(
            ['dnf', '-q', '-y', task], sudo=True))

if __name__ == '__main__':
    dnf_packages: DnfPackages = DnfPackages()
    try:
        dnf_packages.run()
    except lib.UpsetError as error:
        logger.error(error)
        sys.exit(1)
    except KeyError as error:
        logger.error(error)
        sys.exit(1)
