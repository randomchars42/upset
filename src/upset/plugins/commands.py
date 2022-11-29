#!/usr/bin/python3
"""
Plugin to run arbitrary commands in bash.

Examples::

    # Exemplary task description
    {
        "name": "ensure my commands have been run",
        "plugin": "commands",
        "variables": {
            "commands": [
                # describe a group
                {
                    "command": ["echo", "whoami"],
                    "ensure": "run",
                    "sudo": true,
                }
        },
        "foreach": [{
            "user": "user1",
            },],
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

class Commands(lib.Plugin):
    """Run arbitrary commands in bash."""

    def run(self) -> None:
        """Do the main work."""
        for subtask in self.data['variables']['commands']:
            if subtask['ensure'] == 'run':
                self.ensure_run(
                        subtask['command'],
                        subtask.get('sudo', False))
            else:
                raise lib.UpsetError(
                        f'no such subtask "{subtask["ensure"]}"')

    def ensure_run(self, command: list[str], sudo: bool = False):
        """Run the command.

        Args:
            command: The command to run as list of strings.
            sudo: Prepend sudo?
        """
        logger.info('ensuring comand "%s" is run%s',
                    ''.join(command),
                    ' as root' if sudo else '')

        output: str = lib.Sys.run_command(
                lib.Sys.build_command(command, sudo=sudo))
        print(output)

if __name__ == '__main__':
    commands: Commands = Commands()
    try:
        commands.run()
    except lib.UpsetError as error:
        logger.error(error)
        sys.exit(1)
    except KeyError as error:
        logger.error(error)
        sys.exit(1)
