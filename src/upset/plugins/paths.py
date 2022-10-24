#!/usr/bin/python3
"""
Plugin to ensure a certain path exists or does not exist.

Can handle:
 - creation of files from templates
 - creation of directories
 - creation of symlinks
 - ensuring proper permissions (standard UNIX)

Examples::

    # Exemplary task description
    {
        "name": "ensure my paths",
        "plugin": "paths",
        "variables": {
            "paths": [
                # describe a file
                {
                    "path": "/etc/fstab",
                    "ensure": "file",
                    # see `files` below
                    "template": "template1",
                    # mode can be:
                    #  - "force": replace file by template
                    #  - "update": replace file if template is newer
                    #  - "asis": only create file from template if no
                    #       file is present
                    "mode": "update",
                    # permissions `[user, group, mode]`:
                    # an empty string for either the user or the group
                    # will leave the respective property "as is"
                    # if a new file is created, "as is" means
                    # "root:root"
                    "permissions": ["root", "root", 0o644],
                    # create a numbered backup
                    "backup": true,
                },
                # describe a file that has to be present for certain
                # users
                {
                    # see `foreach_variable` below
                    "path": "/home/$user/file",
                    "ensure": "file",
                    "template": "template2",
                    "mode": "update",
                    "permissions": ["$user", "", 0o600],
                    "backup": true,
                },
                # describe a directory
                {
                    "path": "/home/$user/dir",
                    "ensure": "dir",
                    "permissions": ["$user", "", 0o600],
                    "backup": true,
                },
                # describe a symlink
                {
                    "path": "/home/$user/dir",
                    "target": "/home/$user/.hidden/dir",
                    "ensure": "symlink",
                    "backup": true,
                },
                # describe an absent file
                {
                    "path": "/home/$user/dir",
                    "ensure": "absent",
                    "backup": true,
                },
            ],
            "template2": {
                "greeting": "Hello",
            },
        },
        "foreach": ["user1", "user2"],
        "foreach_variable": "user",
        "files": {
            "template1": "/path/to/my/template1",
            # if a file contains variables that are set the variables
            # will be expanded
            # in this case:
            #  - `$greeting` will become "Hello", see
            #    `variables.template2`
            #  - `$user` will be "user1" or "user2" respectively
            "template2": "/template/with/variables",
        }
    }
"""

import logging
import pathlib
import sys

from typing import Any
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

class Paths(lib.Plugin):
    """Deal with path related tasks."""

    def run(self) -> None:
        """Do the main work."""
        for subtask in self.data['variables']['paths']:
            if not 'backup' in subtask:
                subtask['backup'] = True

            match subtask['ensure']:
                case 'absent':
                    self.ensure_absent(subtask)
                case 'file':
                    self.ensure_file(subtask)
                case 'dir':
                    self.ensure_dir(subtask)
                case 'symlink':
                    self.ensure_symlink(subtask)
                case 'other':
                    raise lib.UpsetError(
                            f'no such subtask "{subtask["ensure"]}"')

    def ensure_absent(self, subtask: Any) -> None:
        """Ensure nothing exists at path.

        Args:
            subtask: The object in the `Task.variables.paths` list.
        """
        lib.Fs.remove(pathlib.Path(subtask['path']), subtask['backup'])

    def ensure_file(self, subtask: Any) -> None:
        """Ensure a file is present.

        Args:
            subtask: The object in the `Task.variables.paths` list.
        """
        if 'permissions' in subtask:
            permissions: lib.PermissionSet = lib.PermissionSet(
                    *subtask['permissions'])
        else:
            permissions = lib.PermissionSet('', '', 0o600)

        if (not 'template' in subtask or
                not subtask['template'] in self.data['files']):
            raise lib.UpsetError(f'no template file for "{subtask["file"]}"'
                    f' @ "{self.data["name"]}"')

        file: pathlib.Path = pathlib.Path(
                self.data['files'][subtask['template']])

        if subtask['template'] in self.data['variables']:
            variables: dict[str, str] = \
                    self.data['variables'][subtask['template']]
        else:
            variables = {}

        template: lib.Template = lib.Template(file, variables)

        if 'mode' in subtask:
            mode:str = subtask['mode']
        else:
            mode = 'update'

        lib.Fs.ensure_file(
                pathlib.Path(subtask['path']),
                template,
                permissions,
                mode,
                subtask['backup'])

    def ensure_dir(self, subtask: Any) -> None:
        """Ensure a file is present.

        Args:
            subtask: The object in the `Task.variables.paths` list.
        """
        if 'permissions' in subtask:
            permissions: lib.PermissionSet = lib.PermissionSet(
                    *subtask['permissions'])
        else:
            permissions = lib.PermissionSet('', '', 0o700)

        lib.Fs.ensure_dir(
                pathlib.Path(subtask['path']),
                permissions,
                subtask['backup'])

    def ensure_symlink(self, subtask: Any) -> None:
        """Ensure a file is present.

        Args:
            subtask: The object in the `Task.variables.paths` list.
        """
        lib.Fs.ensure_link(
                pathlib.Path(subtask['path']),
                pathlib.Path(subtask['target']),
                subtask['backup'])

if __name__ == '__main__':
    paths: Paths = Paths()
    try:
        paths.run()
    except lib.UpsetError as error:
        logger.error(error)
        sys.exit(1)
    except KeyError as error:
        logger.error(error)
        sys.exit(1)
