#!/usr/bin/env python3.10
"""Upset a system."""

from __future__ import annotations

import argparse
import getpass
import json
import logging
import pathlib
import pkg_resources

from typing import Any
from upset import lib

logger: logging.Logger = logging.getLogger()

class Task():
    """Describes the minimal variables in a task."""

    def __init__(self, name: str) -> None:
        self.name: str = name
        self.plugin: str = ''
        self.foreach: list[str] = []
        self.foreach_variable: str = ''
        self.variables: dict[str, str] = {}
        self.files: dict[str, str] = {}

    def __iter__(self) -> Any:
        yield from {
            "name": self.name,
            "plugin": self.plugin,
            "foreach": self.foreach,
            "foreach_variable": self.foreach_variable,
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
            raise lib.UpsetError('could not parse task') from error

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

    def run(self, path_plan: str,user: str = '', host: str = '',
            user_plugins: str = '') -> None:
        """Read the plan and execute its task(s).

        Args:
            path_plan: The path to the plan.
            user: The user to authenticate with.
            host: The host to run the tasks on.
            user_plugins: Path to user defined plugins.
        """

        try:
            plan: Tasklist = self.read_plan(pathlib.Path(path_plan))
            password: str = getpass.getpass(f'Password for {user}@{host}:')
            temp_dir: pathlib.Path = lib.Sys.make_temporary_directory(
                    user, host)
            self.send_lib(temp_dir, user, host)

            user_plugins_path: pathlib.Path = (
                    pathlib.Path(user_plugins) if user_plugins != '' else
                    pathlib.Path('~/.config/upset/plugins'))

            task: Task
            for task in plan:
                self.send_plugin(task, temp_dir, user, host, user_plugins_path)
                self.send_files(task, temp_dir, user, host)
                self.run_task(task, temp_dir, user, host, password)
        except lib.UpsetError as error:
            logger.error(error)
        finally:
            try:
                lib.Sys.remove_temporary_directory(temp_dir)
            except lib.UpsetError:
                logger.error('could not clean up temporary directory "%s"',
                        temp_dir)

    def read_plan(self, path: pathlib.Path) -> list[Any]:
        """Read the specified JSON file and validate it as a plan.

        Args:
            path: The path to the file.

        Raises:
            lib.UpsetError: Raised if the plan cannot be accessed or is
                malformed.
        """
        logger.info('reading plan "%s"', str(path))
        try:
            raw: list[Any] = json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError as error:
            raise lib.UpsetError(f'could not read plan "{path}"') from error
        except json.JSONDecodeError as error:
            raise lib.UpsetError(f'invalid plan "{path}"') from error

        tasklist: Tasklist = []

        for item in raw:
            tasklist.append(Task.from_json(item))

        return tasklist

    def send_lib(self, temporary_directory: pathlib.Path, user: str,
            host: str) -> None:
        """Send the library if it has not already been sent.

        Args:
            temporary_directory: The path to the temporary_directory on the
                target machine.
            user: The user to log in with.
            host: The host to execute the task on.

        Raises:
            lib.UpsetError: Raised if the transfer failed.
        """
        logger.info('sending lib')

        try:
            lib.Sys.run_command(
                    lib.Sys.build_scp_command(
                        pathlib.Path(pkg_resources.resource_filename(
                            __name__, 'lib.py')),
                        temporary_directory,
                        direction='to', user=user, host=host))
        except lib.UpsetSysError as error:
            raise lib.UpsetError('could not send lib') from error

    # pylint: disable=too-many-arguments
    def send_plugin(self, task: Task, temporary_directory: pathlib.Path,
            user: str, host: str, user_plugins: pathlib.Path) -> None:
        """Send the required plugin if it has not already been sent.

        Args:
            task: The task that requires the plugin.
            temporary_directory: The path to the temporary_directory on the
                target machine.
            user: The user to log in with.
            host: The host to execute the task on.
            user_plugins: Path to user defined plugins.

        Raises:
            lib.UpsetError: Raised if the plugin could not be found or the
                transfer failed.
        """
        if task.plugin in self._sent_plugins:
            return

        logger.info('sending plugin "%s"', task.plugin)

        try:
            plugin: pathlib.Path = lib.Helper.localise_plugin(task.plugin,
                    [pathlib.Path(
                        pkg_resources.resource_filename(__name__, 'plugins')),
                    user_plugins])
        except lib.UpsetHelperError as error:
            raise lib.UpsetError(
                    f'could not find plugin "{task.plugin}"') from error

        try:
            lib.Sys.run_command(
                    lib.Sys.build_scp_command(
                        plugin,
                        temporary_directory,
                        direction='to', user=user, host=host))
        except lib.UpsetSysError as error:
            raise lib.UpsetError(
                    f'could not send plugin "{task.plugin}"') from error

        self._sent_plugins.append(task.plugin)

    def send_files(self, task: Task, temporary_directory: pathlib.Path,
            user: str, host: str) -> None:
        """Send files required by the task if they have not already been sent.

        Args:
            task: The task that requires the files.
            temporary_directory: The path to the temporary_directory on the
                target machine.
            user: The user to log in with.
            host: The host to execute the task on.

        Raises:
            lib.UpsetError: Raised if the transfer failed.
        """
        for name,file in task.files.items():
            if name in self._sent_files:
                continue
            logger.info('sending file "%s"', file)
            try:
                file_path: pathlib.Path = pathlib.Path(file)
                lib.Sys.run_command(
                        lib.Sys.build_scp_command(
                            file_path,
                            temporary_directory /
                                lib.Helper.create_unique_file_name(file_path),
                            direction='to', user=user, host=host))
            except lib.UpsetSysError as error:
                raise lib.UpsetError(
                        f'could not send file "{file}"') from error
            self._sent_files.append(name)

    # pylint: disable=too-many-arguments
    def run_task(self, task: Task, temporary_directory: pathlib.Path,
            user: str, host: str, password: str,
            python: str = '/usr/bin/python3') -> str:
        """Run the task on the target machine.

        Args:
            task: The task to run.
            temporary_directory: The path to the temporary_directory on the
                target machine.
            user: The user to log in with.
            host: The host to execute the task on.
            password: The password to use `sudo` on the target machine.
            python: The python executable on the target machine.

        Raises:
            lib.UpsetError: Raised if the transfer failed.
        """
        output: str = ''
        try:
            for for_variable in task.foreach:
                output += lib.Sys.run_command(
                        lib.Sys.build_sudo_command([
                            python,
                            str(temporary_directory / f'{task.plugin}.py'),
                            lib.Helper.encode_data(
                                self.transform_task_to_data(task,
                                    for_variable))],
                            password, user, host))
                output += '\n'
        except lib.UpsetSysError as error:
            raise lib.UpsetError(
                    f'could not run plugin "{task.plugin}"') from error
        # return for testing / debugging
        return output

    def transform_task_to_data(self, task: Task, for_variable: str) -> Any:
        """Transform the information in a task for the remote plugin.

        Creates an additional key from the name specified in
        `Task.foreach_variable` and the value passed in as `for_variable`.

        Translates file names to the names on the remote machine using the same
        algorithm as `upset.send_files()`.

        Args:
            task: The task to transform.
            for_variable: The current value of `Task.foreach` which will become
                the value of the new key wich name is specified by
                `Task.foreach_variable`.
        """
        data: Any = {
                task.foreach_variable: for_variable,
                'variables': task.variables.copy(),
                'files': task.files.copy()
                }

        for name, file in data['files'].items():
            data['files'][name] = lib.Helper.create_unique_file_name(
                    pathlib.Path(file))

        return data

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
