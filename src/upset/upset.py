#!/usr/bin/env python3.10
"""Upset."""

from __future__ import annotations

import argparse
import base64
import getpass
import json
import logging
import pathlib
import subprocess

from typing import Any

logger: logging.Logger = logging.getLogger()

class UpsetError(Exception):
    """Custom exception."""

class Task():
    """Describes the minimal variables in a task."""

    def __init__(self, name: str) -> None:
        self.name: str = name
        self.plugin: str = ''
        self.foreach: list[str] = []
        self.variables: dict[str, str] = {}
        self.files: dict[str, str] = {}

    def __iter__(self) -> Any:
        yield from {
            "name": self.name,
            "plugin": self.plugin,
            "foreach": self.foreach,
            "variables": self.variables,
            "files": self.files
        }.items()

    def __str__(self) -> str:
        return json.dumps(dict(self), ensure_ascii=False)

    def __repr__(self) -> str:
        return self.__str__()

    def to_json(self) -> str:
        """Turn an instance of this class into a JSON string.

        Returns:
            A valid JSON string
        """
        return str(self)

    @staticmethod
    def from_json(json_object) -> Task:
        """Convert JSON to an instance of this class.

        Args:
            json_object: JSON to convert.

        Returns:
            A corresponding instance.
        """
        try:
            task = Task(json_object['name'])
            for name in task.__dict__:
                if name in json_object:
                    setattr(task, name, json_object[name])
            return task
        except KeyError as error:
            raise UpsetError('could not parse task') from error

Tasklist = list[Task]

class Upset:
    """
    Attributes:
        _sent_plugins: A list of plugins already sent so the files need not be
            sent more than once.
        _sent_files: A list of files already sent so the files need not be
            sent more than once.
    """

    def __init__(self) -> None:
        """Initialise class attributes."""
        self._sent_plugins: list[str] = []
        self._sent_files: list[str] = []

    def run(self, path_plan: str, user: str, host: str) -> None:
        """Read the plan and execute its task(s).

        Args:
            path_plan: The path to the plan.
            user: The user to authenticate with.
            host: The host to run the tasks on.
        """

        password: str = getpass.getpass()

        try:
            task: Task
            for task in self.read_plan(pathlib.Path(path_plan)):
                self.send_plugin(task)
                self.send_files(task)
                self.run_task(task, user, host, password)
        except UpsetError as error:
            logger.error(error)

    def read_plan(self, path: pathlib.Path) -> list[Any]:
        """Read the specified JSON file and validate it as a plan.

        Args:
            path: The path to the file.
        """
        logger.info('reading plan "%s"', str(path))
        try:
            raw: list[Any] = json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError as error:
            raise UpsetError(f'could not read plan "{path}"') from error
        except json.JSONDecodeError as error:
            raise UpsetError(f'invalid plan "{path}"') from error

        tasklist: Tasklist = []

        for item in raw:
            tasklist.append(Task.from_json(item))

        return tasklist

    def send_plugin(self, task: Task) -> None:
        """Send the required plugin if it has not already been sent.

        Args:
            task: The task that requrires the plugin.
        """
        if task.plugin in self._sent_plugins:
            return

        logger.info('sending plugin "%s"', task.plugin)

    def send_files(self, task: Task) -> None:
        """Send files required by the task if they have not already been sent.

        Args:
            task: The task that requrires the plugin.
        """
        for file in task.files:
            if file in self._sent_files:
                continue
            logger.info('sending file "%s"', file)

    def run_command(self, command_parts: list[str]) -> str:
        """Run a command as a subprocess.

        Args:
            command_parts: The command with parameters, each in its own string.

        Returns:
            Output of the command (without final `"\n"`).

        Raises:
            UpsetError: Raised if the remote command fails.
        """
        try:
            return subprocess.check_output(command_parts).decode().strip()
        except ChildProcessError as error:
            raise UpsetError(
                    f'command "{command_parts}" returned an error') from error

    def build_sudo_command(self,
            command_parts: list[str], password: str) -> list[str]:
        """Prepare a command to be run with sudo non-interactively.

        Achieves this by making `sudo` read the password from `stdin` (`-S`) and
        without a promt (`--prompt=`). The password is `echo`ed and piped into
        `sudo`s `stdin`.

        To avoid having to deal with escaping issues the sequence
        `echo "{password}" | sudo -S --prompt= -- {command}` is encoded as
        `base64` (as suggested by "ThoriumBR" on
        <https://serverfault.com/questions/625641>).

        At the target the encoded sequence gets decoded by piping it to
        `base64 -d` and evaluating the output in the `$SHELL`.

        Beware: The command parts are simply joined with `" ".join(command)`.
        The behaviour might differ from `subprocess.check_output(command)`!

        Args:
            command_parts: The command to run with its parameters, each in its
                own string.
            password: The password to use with `sudo`.

        Returns:
            A command that can be passed to a shell but must be interpreted,
                e.g., `bash -c "COMMAND"` or `ssh USER@HOST "COMMAND"`. Although
                the return value is a list it only holds one string containing
                the whole command. This is done for consistency / convenience.
        """
        command: str = ' '.join(command_parts)
        # base64.b64encode() needs a byte-like argument so the string is first
        # "encoded"
        encoded_command: bytes = base64.b64encode(
                f'echo "{password}" | sudo -S --prompt= -- {command}'.encode())
        # the result is a bytestream so it is "decoded" to a string
        # but it is still base64-gibberish
        return [f'echo {encoded_command.decode()} | base64 -d | $SHELL']

    def build_remote_command(self, command_parts: list[str], user: str,
            host: str) -> list[str]:
        """Run a command on a remote host.

        Args:
            command_parts: The command with parameters to run on `host`, each as
                its own string.
            user: The user to loggon to root.
            host: The host to execute the task on.
        """
        return ['ssh', f'{user}@{host}'] + command_parts

def main() -> None:
    """Reads cli arguments and runs the main loop."""

    parser = argparse.ArgumentParser()
    parser.add_argument('-v',
                        '--verbosity',
                        help='increase verbosity',
                        action='count',
                        default=0)

    args = parser.parse_args()

    levels: list[str] = ['ERROR', 'WARNING', 'INFO', 'DEBUG']
    # there are only levels 0 to 3
    # everything else will cause the index to be out of bounds
    verbosity_level: int = min(args.verbosity, 3)
    logger.setLevel(levels[verbosity_level])

    upset: Upset = Upset()

if __name__ == '__main__':
    main()
