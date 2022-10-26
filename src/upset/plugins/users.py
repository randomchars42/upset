#!/usr/bin/python3
"""
Plugin to ensure users exist.

Can handle:
 - creation of users
 - deletion of users
 - ensuring users are in groups (that already exist)

Examples::

    # Exemplary task description
    {
        "name": "ensure my users",
        "plugin": "users",
        "variables": {
            "users": [
                # describe a group
                {
                    "name": "{name}",
                    "ensure": "group",
                    "id": "{id}",
                },
                # describe a group that must not be present
                {
                    "name": "{group}",
                    "ensure": "group_absent",
                },
                # describe a user
                {
                    "name": "{name}",
                    "ensure": "user",
                    # if no uid is given the system will choose one
                    "id": "{id}",
                    # put user in group instead of creating a group for
                    # the user
                    # make sure the group exists
                    # leave empty for system default
                    "group": "{group}",
                    # comma separated user information in the following
                    # order:
                    # Real Name,Address,Work Phone,Home Phone,Other
                    "gecos": "{gecos}",
                    # use path as home instead of /home/USER
                    # leave empty for system default
                    "home": "{home}",
                    # the encrypted password
                    # use `openssl passwd -1` or `crypt`
                    # if not set the account is blocked until root sets
                    # a
                    # password
                    "password": "{password}"
                },
                # describe a user that must not be present
                {
                    "name": "{name}",
                    "ensure": "user_absent",
                },
                # ensure user is in groups
                {
                    "name": "{name}",
                    "ensure": "in_groups",
                    "groups": ["{group}"],
                },
        },
        "foreach": [{
            "name": "user1",
            "id": 4201,
            "group": "nicergroup"
            "gecos": "User 1,,,,",
            "home": "/nicerhome/user1",
            "password": "$1$FLV0AoCl$sPzvwJwKLMm2wXfmCYUYk1",
            },],
        },
    }
"""
import grp
import logging
import pwd
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

class Users(lib.Plugin):
    """Handle creation / deletion of users."""

    def run(self) -> None:
        """Do the main work."""
        for subtask in self.data['variables']['users']:
            if subtask['ensure'] == 'user':
                self.ensure_user(
                        subtask['name'],
                        subtask.get('uid', ''),
                        subtask.get('group', ''),
                        subtask.get('gecos', ''),
                        subtask.get('password', ''))
            elif subtask['ensure'] == 'user_absent':
                self.ensure_user_absent(subtask['name'])
            elif subtask['ensure'] == 'group':
                self.ensure_group(subtask)
            elif subtask['ensure'] == 'group_absent':
                self.ensure_group_absent(subtask)
            elif subtask['ensure'] == 'in_group':
                self.ensure_in_group(subtask['name'], subtask['group'])
            elif subtask['ensure'] == 'not_in_group':
                self.ensure_not_in_group(subtask['name'], subtask['group'])
            else:
                raise lib.UpsetError(
                        f'no such subtask "{subtask["ensure"]}"')

    def user_exists(self, name: str) -> bool:
        """Test if the user exists on the system.

        Args:
            name: The user's name.

        Returns:
            `True` if the user exists else `False`.
        """
        usernames: list[str] = [x[0] for x in pwd.getpwall()]
        return name in usernames

    def group_exists(self, name: str) -> bool:
        """Test if the group exists on the system.

        Args:
            name: The group's name.

        Returns:
            `True` if the group exists else `False`.
        """
        groupnames: list[str] = [x[0] for x in grp.getgrall()]
        return name in groupnames

    def user_in_group(self, name: str, group: str) -> bool:
        """Test wether a user is in a group.

        Args:
            name: The user's name.
            group: The group's name.

        Returns:
            `True` if the `name` is in `group` else `False`.
        """
        if not self.user_exists(name):
            raise lib.UpsetError(f'no such user "{name}"')
        if not self.group_exists(group):
            raise lib.UpsetError(f'no such group "{group}"')
        group_info: grp.struct_group = grp.getgrnam(group)
        user = pwd.getpwnam(name)
        # see if the group is the primary group -> check user object
        # see if it is a secondary group -> check group-members
        return group_info.gr_gid == user.pw_gid or name in group_info.gr_mem

    def ensure_user(self, name: str, uid: str = '', group: str = '',
            gecos: str = ',,,,', password: str = ''):
        """Create an user.

        Args:
            name: The name of the user (see `man adduser` for allowed
                names).
            uid: The user id. If an empty string is given `adduser` will
                choose an id.
            group: A group for the user. If an empty string is given
                a group with the user's name is created.
            gecos: Ancient information about the user in the form of:
                "Real Name,Address,Work Phone, Home Phone,Other/Email".
            password: A password for the user. Must be encrypted (e.g.
                using `openssl passwd -1`). If an empty string is given
                the user's login will be blocked until `root` sets a
                password.
        """
        logger.info('ensuring user "%s" exists', name)

        if self.user_exists(name):
            return

        command = ['/usr/sbin/adduser', '--disabled-password']

        if uid != '':
            command.extend(['--uid', uid])

        if group != '':
            command.extend(['--ingroup', group])

        if gecos != '':
            command.extend(['--gecos', gecos])

        command.append(name)

        logger.info('creating user "%s"', name)

        lib.Sys.run_command(lib.Sys.build_command(command, sudo=True))

        if password != '':
            logger.info('setting password for user "%s"', name)

            lib.Sys.run_command(lib.Sys.build_command([
                '/usr/sbin/usermod', '--password', password, name], sudo=True))

    def ensure_user_absent(self, name: str) -> None:
        """Ensure a username is not used.

        Args:
            name: The user's name.
        """
        logger.info('ensuring user "%s" is absent', name)

        if not self.user_exists(name):
            return

        logger.info('deleting user "%s"', name)

        lib.Sys.run_command(lib.Sys.build_command(['/usr/sbin/deluser', name],
            sudo=True))

    def ensure_group(self, name: str, gid: str = ''):
        """Create a group.

        Args:
            name: The name of the group (see `man addgroup` for allowed
                names).
            gid: The group id. If an empty string is given `addgroup`
                will choose an id.
        """
        logger.info('ensuring group "%s" exists', name)

        if self.group_exists(name):
            return

        command = ['/usr/sbin/addgroup']

        if gid != '':
            command.extend(['--gid', str(gid)])

        command.append(name)

        logger.info('creating group "%s"', name)

        lib.Sys.run_command(lib.Sys.build_command(command, sudo=True))

    def ensure_group_absent(self, name: str) -> None:
        """Ensure a group is absent.

        Args:
            name: The group's name.
        """
        logger.info('ensuring group "%s" is absent', name)

        if not self.group_exists(name):
            return

        logger.info('deleting group "%s"', name)

        lib.Sys.run_command(lib.Sys.build_command(['/usr/sbin/delgroup', name],
            sudo=True))

    def ensure_in_group(self, name: str, group: str) -> None:
        """Ensure user is in the given group.

        Args:
            name: The user's name.
            group: The group's name.
        """
        logger.info('ensuring user "%s" is in group "%s"', name, group)

        if self.user_in_group(name, group):
            return

        logger.info('adding user "%s" to group "%s"', name, group)

        lib.Sys.run_command(lib.Sys.build_command(
            ['/usr/sbin/adduser', name, group], sudo=True))

    def ensure_not_in_group(self, name, group):
        """Ensure user is not in the given group.

        Args:
            name: The user's name.
            group: The group's name.
        """
        logger.info('ensuring user "%s" is not in group "%s"', name, group)

        if not self.user_in_group(name, group):
            return

        logger.info('removing user "%s" from group "%s"', name, group)

        lib.Sys.run_command(lib.Sys.build_command(
            ['/usr/sbin/deluser', name, group], sudo=True))

if __name__ == '__main__':
    users: Users = Users()
    try:
        users.run()
    except lib.UpsetError as error:
        logger.error(error)
        sys.exit(1)
    except KeyError as error:
        logger.error(error)
        sys.exit(1)
