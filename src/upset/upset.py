#!/usr/bin/env python3.9
"""Upset a system."""

from __future__ import annotations

import argparse
import getpass
import json
import logging
import pathlib
import pkg_resources
import sys
import traceback

from typing import Any
from upset import lib

logger: logging.Logger = logging.getLogger(__name__)

class Task():
    """Describes the minimal variables in a task."""

    def __init__(self, name: str) -> None:
        self.name: str = name
        self.plugin: str = ''
        self.foreach: list[dict[str, str]] = []
        self.variables: dict[str, Any] = {}
        self.files: dict[str, str] = {}

    def __iter__(self) -> Any:
        yield from {
            'name': self.name,
            'plugin': self.plugin,
            'foreach': self.foreach,
            'variables': self.variables,
            'files': self.files
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
        _sent_plugins: A list of plugins already sent so the files need
            not be sent more than once.
        _sent_files: A list of files already sent so the files need not
            be sent more than once.
    """

    def __init__(self) -> None:
        """Initialise class attributes."""
        self._sent_plugins: list[str] = []
        self._sent_files: list[str] = []

    def run(self, path_plan: str, user: str = '', host: str = '',
            ssh_key_path: str = '', user_plugins_dir: str = '') -> None:
        """Read the plan and execute its task(s).

        Args:
            path_plan: The path to the plan.
            user: The user to authenticate with.
            host: The host to run the tasks on.
            ssh_key_path: The ssh key or identity to use.
            user_plugins_dir: Path to user defined plugins.
        """
        temp_dir: pathlib.Path = pathlib.Path()
        password: str = ''
        try:
            # read the plan
            plan: Tasklist = self.read_plan(pathlib.Path(path_plan))

            # the plugins are called as super user on the target machine
            password = getpass.getpass(f'Password for {user}@{host}:')

            # use ssh key for authentication on the target machine
            if ssh_key_path == '':
                ssh_key: pathlib.Path = pathlib.Path(f'~/.ssh/{host}')
            else:
                ssh_key = pathlib.Path(ssh_key_path).resolve()
            # make sure the ssh key exists
            # TODO find a way to do this non-interactively
            lib.Sys.ensure_ssh_key(user, host, ssh_key)

            # create a temporary directory
            temp_dir = lib.Sys.make_temporary_directory(
                    user, host, ssh_key)
            # send the library to the target machine
            self.send_lib(temp_dir, user, host, ssh_key)
            # determine the path to the user provided plugins
            # use fallback if none is provided
            user_plugins_path: pathlib.Path = (
                    pathlib.Path(user_plugins_dir)
                    if user_plugins_dir != '' else
                    pathlib.Path('~/.config/upset/plugins'))

            task: Task
            for task in plan:
                # send plugin to the target machine
                # plugins that have already been sent are not sent
                # twice (see Upset._sent_plugins)
                self.send_plugin(task, temp_dir, user, host, ssh_key,
                        user_plugins_path)
                # run task for every set of variables in `task.foreach`
                # if it is empty provide a fake task
                if len(task.foreach) == 0:
                    task.foreach = [{}]
                for var in task.foreach:
                    # replace all variables in the task description
                    expanded_task: Task = self.expand_task(task, var)
                    # send the necessary files to the target machine
                    # the files might contain variables that are
                    # expanded differently for every iteration
                    # so the call to `Upset.send_files()` is in the loop
                    # files that have already been sent are not sent
                    # twice (see Upset._sent_files)
                    self.send_files(expanded_task, temp_dir, user, host,
                            ssh_key)
                    # run the task
                    output: str = self.run_task(expanded_task, temp_dir, user,
                            host, ssh_key, password, var)
                    print(output)
        except lib.UpsetError as error:
            logger.error(error)
            print(error)
            traceback.print_exc(file=sys.stdout)
        except KeyboardInterrupt:
            logger.warning('recieved interrupt, stopping')
        finally:
            try:
                if str(temp_dir) == str(pathlib.Path()):
                    # this would happen if the temporary directory has
                    # not yet been created
                    # do not attempt to remove the current directory
                    logger.info('no temporary directory to clean up')
                else:
                    lib.Sys.remove_temporary_directory(temp_dir, password, user,
                            host, ssh_key)
            except lib.UpsetError:
                logger.error('could not clean up temporary directory "%s"',
                        temp_dir)
                traceback.print_exc(file=sys.stdout)

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
            host: str, ssh_key: pathlib.Path = pathlib.Path()) -> None:
        """Send the library if it has not already been sent.

        Args:
            temporary_directory: The path to the temporary_directory on
                the target machine.
            user: The user to log in with.
            host: The host to execute the task on.
            ssh_key: The ssh key or identity to use.

        Raises:
            lib.UpsetError: Raised if the transfer failed.
        """
        logger.info('sending lib')

        try:
            lib.Sys.run_command(
                    lib.Sys.build_scp_command(
                        pathlib.Path(pkg_resources.resource_filename(
                            __name__, '__init__.py')),
                        temporary_directory,
                        direction='to', user=user, host=host, ssh_key=ssh_key))
            lib.Sys.run_command(
                    lib.Sys.build_scp_command(
                        pathlib.Path(pkg_resources.resource_filename(
                            __name__, 'lib.py')),
                        temporary_directory,
                        direction='to', user=user, host=host, ssh_key=ssh_key))
        except lib.UpsetSysError as error:
            raise lib.UpsetError('could not send lib') from error

    def expand_task(self, task: Task, var: dict) -> Task:
        """Expand all variables named in `var.keys()`.

        Args:
            task: The task to expand.
            var: The variables to replace.
        """
        if not var:
            return task

        # copy only
        new_task: Task = Task(task.name)
        new_task.plugin = task.plugin
        # expand
        new_task.variables = self.expand_task_leaves(task.variables, var)
        new_task.files = self.expand_task_leaves(task.files, var)

        return new_task

    def expand_task_leaves(self, leaf: Any, var: dict) -> Any:
        """Traverse lists and dictionarys and expand variables.

        Args:
            leaf: Portion of a JSON object.
            var: String to replace `"{}"` or dictionary containing all
                necessary keys.
        """
        try:
            if isinstance(leaf, str):
                return leaf.format(**var)
            elif isinstance(leaf, list):
                return [self.expand_task_leaves(item, var) for item in leaf]
            elif isinstance(leaf, dict):
                return {self.expand_task_leaves(key, var):
                        self.expand_task_leaves(value, var)
                        for key, value in leaf.items()}
            else:
                return leaf
        except KeyError as error:
            raise lib.UpsetError(
                    f'No key in "{var}" to format "{leaf}"') from error
        except IndexError as error:
            raise lib.UpsetError(
                    f'No substitute in "{var}" to format "{leaf}"') from error

    # pylint: disable=too-many-arguments
    def send_plugin(self, task: Task, temporary_directory: pathlib.Path,
            user: str, host: str, ssh_key: pathlib.Path = pathlib.Path(),
            user_plugins: pathlib.Path = pathlib.Path()) -> None:
        """Send the required plugin if it has not already been sent.

        Args:
            task: The task that requires the plugin.
            temporary_directory: The path to the temporary_directory on
                the target machine.
            user: The user to log in with.
            host: The host to execute the task on.
            ssh_key: The ssh key or identity to use.
            user_plugins: Path to user defined plugins.

        Raises:
            lib.UpsetError: Raised if the plugin could not be found or
                the transfer failed.
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
                        direction='to', user=user, host=host, ssh_key=ssh_key))
        except lib.UpsetSysError as error:
            raise lib.UpsetError(
                    f'could not send plugin "{task.plugin}"') from error

        self._sent_plugins.append(task.plugin)

    def send_files(self, task: Task, temporary_directory: pathlib.Path,
            user: str, host: str,
            ssh_key: pathlib.Path = pathlib.Path()) -> None:
        """Send files to target if they have not already been sent.

        Args:
            task: The task that requires the files.
            temporary_directory: The path to the temporary_directory on
                the target machine.
            user: The user to log in with.
            host: The host to execute the task on.
            ssh_key: The ssh key or identity to use.

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
                            direction='to', user=user, host=host,
                            ssh_key=ssh_key))
            except lib.UpsetSysError as error:
                raise lib.UpsetError(
                        f'could not send file "{file}"') from error
            self._sent_files.append(name)

    # pylint: disable=too-many-arguments
    def run_task(self, task: Task, temporary_directory: pathlib.Path,
            user: str, host: str, ssh_key: pathlib.Path,
            password: str, for_task: dict[str, str],
            python: str = 'python3') -> str:
        """Run the task on the target machine.

        Args:
            task: The task to run.
            temporary_directory: The path to the temporary_directory on
                the target machine.
            user: The user to log in with.
            host: The host to execute the task on.
            ssh_key: The ssh key or identity to use.
            password: The password to use `sudo` on the target machine.
            for_task: The current value(s) of `Task.foreach` which
                will be added to the task.
            python: The python executable on the target machine.

        Raises:
            lib.UpsetError: Raised if the transfer failed.
        """
        try:
            logger.info('running task "%s" for "%s"', task.name,
                    str(for_task))
            command: str = (f'cd {temporary_directory.parent} && '
                        f'{python} -m '
                        f'upset.{task.plugin} ')
            command += lib.Helper.encode_data(
                            self.transform_task_to_data(task, for_task))
            return lib.Sys.run_command(
                    lib.Sys.build_sudo_command([
                        'bash', '-c ', f'"{command}"'],
                        password, user, host, ssh_key))
        except lib.UpsetSysError as error:
            raise lib.UpsetError(
                    f'could not run plugin "{task.plugin}"') from error

    def transform_task_to_data(self, task: Task, for_variable: dict) -> Any:
        """Transform the information in a task for the remote plugin.

        Creates an additional key from the name specified in
        `Task.foreach_variable` and the value passed in as
        `for_variable`.

        Translates file names to the names on the remote machine using
        the same algorithm as `upset.send_files()`.

        Args:
            task: The task to transform.
            for_variable: The current value(s) of `Task.foreach` which
                will be added to the task.
        """
        for name, file in task.files.items():
            task.files[name] = lib.Helper.create_unique_file_name(
                    pathlib.Path(file))

        return {
                'name': task.name,
                'plugin': task.plugin,
                'variables': task.variables,
                'files': task.files,
                'for': for_variable
                }

def main() -> None:
    """Reads cli arguments and runs the main loop."""

    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('plan',
            help='the plan to execute')
    parser.add_argument('-u',
            '--user',
            help='the user on the remote machine',
            default='')
    parser.add_argument('-t',
            '--target',
            help='the hostname of the remote machine',
            default='')
    parser.add_argument('-k',
            '--ssh_key',
            help='the ssh key to log into the remote machine',
            default='')
    parser.add_argument('-p',
            '--plugins',
            help='the path where additional plugins could be found',
            default='')
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
    logging_handler: logging.StreamHandler = logging.StreamHandler()
    logging_handler.setLevel(logging.DEBUG)
    logging_formatter = logging.Formatter('%(levelname)s %(name)s %(message)s')
    logging_handler.setFormatter(logging_formatter)
    root_logger: logging.Logger = logging.getLogger()
    root_logger.setLevel(logging.ERROR)
    root_logger.addHandler(logging_handler)
    root_logger.setLevel(levels[verbosity_level])

    upset: Upset = Upset()
    upset.run(path_plan=args.plan, user=args.user, host=args.target,
            ssh_key_path=args.ssh_key, user_plugins_dir=args.plugins)

if __name__ == '__main__':
    main()
