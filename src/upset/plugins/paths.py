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

import pathlib

from upset import lib
