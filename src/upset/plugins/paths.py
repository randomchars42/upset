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
                    # permissions `"user,group,mode"`:
                    # a "-" means for either the user, the group or the
                    # mode will leave the respective property "as is"
                    # if a new file is created, "as is" means
                    # "root:root" and the mode as
                    # a "." for either property means take the value of
                    # the parent (only makes sense for directories)
                    # if you want to be more specific spefiy a value
                    # probably using a variable, e.g.,
                    # "{user},{group},-"
                    # "-" is short for "-,-,-"
                    # "." is short for ".,.,."
                    "permissions": "root,root,644",
                    # create a numbered backup
                    "backup": true,
                },
                # describe a file that has to be present for certain
                # users
                {
                    # see `foreach_variable` below
                    "path": "/home/{user}/file",
                    "ensure": "file",
                    "template": "template2",
                    "mode": "update",
                    "permissions": "{user},{group},600",
                    "backup": true,
                },
                # decribe a file that must exist and contain defined
                # text
                # can be used to search and replace text (regular
                # expression) in a file
                # the default is to insert the line at the end ("")
                {
                    "path": "/home/{user}/file",
                    "ensure": "in_file",
                    "text": "some text",
                    "insert_at": "",
                    "backup": true,
                },
                # describe a directory
                {
                    "path": "/home/{user}/dir",
                    "ensure": "dir",
                    "permissions": "{user},.,600",
                    "backup": true,
                },
                # describe a path
                # you need to specify permissions for each node except
                # root
                {
                    "path": "/home/{user}/long/path/to/ensure",
                    "ensure": "path",
                    "permissions": "/-/-/{user},{group},700,./././.",
                    "backup": true,
                },
                # describe a symlink
                {
                    "path": "/home/{user}/dir",
                    "target": "/home/{user}/.hidden/dir",
                    "ensure": "symlink",
                    "backup": true,
                },
                # describe an absent file
                {
                    "path": "/home/{user}/dir",
                    "ensure": "absent",
                    "backup": true,
                },
            ],
            "template2": {
                "greeting": "Hello",
            },
        },
        "foreach": [{"user": "user1", "group": "group1"},
            {"user": "user2", "group": "group2"}],
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

            if subtask['ensure'] == 'absent':
                self.ensure_absent(subtask)
            elif subtask['ensure'] == 'file':
                self.ensure_file(subtask)
            elif subtask['ensure'] == 'dir':
                self.ensure_dir(subtask)
            elif subtask['ensure'] == 'path':
                self.ensure_path(subtask)
            elif subtask['ensure'] == 'symlink':
                self.ensure_symlink(subtask)
            elif subtask['ensure'] == 'in_file':
                self.ensure_in_file(subtask)
            else:
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
            permissions: str = subtask['permissions']
        else:
            permissions = '.,.,600'

        if (not 'template' in subtask or
                not subtask['template'] in self.data['files']):
            raise lib.UpsetError(f'no template file for "{subtask["file"]}"'
                    f' @ "{self.data["name"]}"')

        file: pathlib.Path = pathlib.Path(
                self.data['files'][subtask['template']])

        if subtask['template'] in self.data['variables']:
            self.data['for'].update(self.data['variables'][subtask['template']])

        template: lib.Template = lib.Template(file, self.data['for'])

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
        """Ensure a directory is present.

        Args:
            subtask: The object in the `Task.variables.paths` list.
        """
        if 'permissions' in subtask:
            permissions: str = subtask['permissions']
        else:
            permissions = '.,.,700'

        lib.Fs.ensure_dir(
                pathlib.Path(subtask['path']),
                permissions,
                subtask['backup'])

    def ensure_path(self, subtask: Any) -> None:
        """Ensure a path is present.

        The permissions will be applied to ...... TODO

        Args:
            subtask: The object in the `Task.variables.paths` list.
        """
        if 'permissions' in subtask:
            permissions: str = subtask['permissions']
        else:
            raise lib.UpsetError('no permissions specified for path '
                    f'"{subtask["path"]}"')

        lib.Fs.ensure_path(
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

    def ensure_in_file(self, subtask: Any) -> None:
        """Ensure certain text is contained by a file.

        Args:
            subtask: The object in the `Task.variables.paths` list.
        """
        if not 'insert_at' in subtask or subtask['insert_at'] == '':
            subtask['insert_at'] = r'\Z'
        lib.Fs.ensure_in_file(
                pathlib.Path(subtask['path']),
                subtask['text'],
                subtask['insert_at'],
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
