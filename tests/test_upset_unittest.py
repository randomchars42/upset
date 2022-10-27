"""Test Upset."""

import getpass
import json
import logging
import logging.config
import os
import pathlib
import unittest

from typing import Any
from upset import lib
from upset import upset

# create console handler and set level to debug
logging_handler: logging.StreamHandler = logging.StreamHandler()
logging_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(levelname)s %(name)s %(message)s')
logging_handler.setFormatter(formatter)
root_logger: logging.Logger = logging.getLogger()
root_logger.setLevel(logging.ERROR)
root_logger.addHandler(logging_handler)
logger: logging.Logger = logging.getLogger(__name__)

levels: list[str] = ['ERROR', 'WARNING', 'INFO', 'DEBUG']
# there are only levels 0 to 3
# everything else will cause the index to be out of bounds
root_logger.setLevel(
        levels[min(int(os.environ.get('UPSET_VERBOSITY', 1)), 3)])
# enable tests that need interaction with the user
require_interaction: bool = bool(os.environ.get('UPSET_INTERACTION', 0))

# pylint: disable=too-many-public-methods
class TestUpsetUpset(unittest.TestCase):
    """Test Upset from upset."""

    def setUp(self) -> None:
        """Add test directory, instantiate class and build fake task."""
        self._upset: upset.Upset = upset.Upset()
        self._base_dir: pathlib.Path = pathlib.Path('tests/tmp')
        self._task: upset.Task = upset.Task.from_json({
                'name': 'faketask',
                'plugin': 'fakeplugin',
                'variables': {
                    'var_1': 'Var 1',
                    'var_2': 'Var 2'
                    },
                'foreach': [{'file': 'a'}, {'file': 'b'}],
                'files': {
                    'template_a': str(self._base_dir / 'template_a'),
                    'template_b': str(self._base_dir / 'template_b'),
                    }
                })
        try:
            self._base_dir.mkdir()
        except OSError:
            logger.debug('could not create "%s"', self._base_dir)

    def tearDown(self) -> None:
        """Remove files."""
        for file in self._base_dir.glob('*'):
            try:
                if file.is_dir():
                    file.rmdir()
                else:
                    file.unlink()
            except OSError:
                logger.debug('could not remove "%s"', file)
        try:
            self._base_dir.rmdir()
        except OSError:
            logger.debug('could not remove "%s"', self._base_dir)

    def test_read_plan(self) -> None:
        """Read a plan."""
        plan: pathlib.Path = self._base_dir / 'plan'
        plan.write_text('[{"name": "a", "plugin": "c"},{"name": "b"}]',
                encoding='utf-8')
        tasklist: list[Any] = self._upset.read_plan(plan)
        self.assertTrue(len(tasklist) == 2)
        self.assertTrue(tasklist[0].name == 'a')
        self.assertTrue(tasklist[0].plugin == 'c')
        self.assertTrue(tasklist[1].name == 'b')

    def test_read_plan_fail_missing(self) -> None:
        """Fail because of missing / inaccessible plan."""
        plan: pathlib.Path = self._base_dir / 'plan'
        with self.assertRaises(lib.UpsetError):
            self._upset.read_plan(plan)

    def test_read_plan_fail_json(self) -> None:
        """Fail because of misshapen JSON."""
        plan: pathlib.Path = self._base_dir / 'plan'
        plan.write_text('[{"name": "a",{"name": "b"}]', encoding='utf-8')
        with self.assertRaises(lib.UpsetError):
            self._upset.read_plan(plan)

    def test_send_lib(self) -> None:
        """Send lib."""
        self._upset.send_lib(self._base_dir, user='', host='')
        self.assertTrue(pathlib.Path(self._base_dir / 'lib.py').exists())

    def test_send_plugin(self) -> None:
        """Send plugin."""
        pathlib.Path(self._base_dir / 'tmp').mkdir()
        pathlib.Path(self._base_dir / 'tmp' / 'fakeplugin.py').touch()
        self._upset.send_plugin(self._task, self._base_dir, user='', host='',
                user_plugins=self._base_dir / 'tmp')
        self.assertTrue(pathlib.Path(self._base_dir / 'fakeplugin.py').exists())
        pathlib.Path(self._base_dir / 'tmp' / 'fakeplugin.py').unlink()

    def test_send_files(self) -> None:
        """Send files."""
        local_a: pathlib.Path = self._base_dir / 'template_a'
        local_a.touch()
        local_b: pathlib.Path = self._base_dir / 'template_b'
        local_b.touch()
        self._upset.send_files(self._task, self._base_dir, user='', host='')
        self.assertTrue(pathlib.Path(
            self._base_dir / lib.Helper.create_unique_file_name(local_a)
            ).exists())
        self.assertTrue(pathlib.Path(
            self._base_dir / lib.Helper.create_unique_file_name(local_b)
            ).exists())

    def test_transform_task_to_data(self) -> None:
        """Transform a task to data that can be used in the plugin."""
        self.assertEqual(
                json.dumps(self._upset.transform_task_to_data(self._task,
                    {'file': 'a'})),
                json.dumps({
                    'name': 'faketask',
                    'plugin': 'fakeplugin',
                    'variables': {
                        'var_1': 'Var 1',
                        'var_2': 'Var 2'
                        },
                    'files': {
                        'template_a': '___'.join(pathlib.Path(self._base_dir /
                            'template_a').resolve().parts[1:]),
                        'template_b': '___'.join(pathlib.Path(self._base_dir /
                            'template_b').resolve().parts[1:]),
                        },
                    'for': {'file': 'a'},
                    }))

    def test_expand_task_dummy(self) -> None:
        """`expand_task()` does not expand on empty var."""
        self.assertEqual(
                self._upset.expand_task(self._task, {}),
                self._task)

    def test_expand_task(self) -> None:
        """Expand task recursively."""
        self.assertEqual(
                str(self._upset.expand_task(upset.Task.from_json({
                    'name': 'faketask',
                    'plugin': 'fakeplugin',
                    'variables': {
                        'var_1': '{user}',
                        'var_2': '{group}',
                        },
                    'files': {
                        'template_{user}': 'file_{user}',
                        'template_b': 'file_{user}_b',
                        },
                    }),
                    {'user': 'user1', 'group': 'group1'})),
                    json.dumps({
                        'name': 'faketask',
                        'plugin': 'fakeplugin',
                        'foreach': [], # upset.Task creates an empty list
                        'variables': {
                            'var_1': 'user1',
                            'var_2': 'group1',
                            },
                        'files': {
                            'template_user1': 'file_user1',
                            'template_b': 'file_user1_b',
                            },
                        }))

    def test_expand_task_fail(self) -> None:
        """Fail expanding task recursively because of unset variable."""
        with self.assertRaises(lib.UpsetError):
            self._upset.expand_task(upset.Task.from_json({
                'name': 'faketask',
                'plugin': 'fakeplugin',
                'variables': {
                    'var_1': '{user}',
                    'var_2': '{group}',
                    'var_3': '{unset}'
                    },
                'files': {
                    'template_{user}': 'file_{user}',
                    'template_b': 'file_{user}_b',
                    },
                }),
                {'user': 'user1', 'group': 'group1'})

    @unittest.skipUnless(require_interaction,
            'do not require interaction with the user')
    def test_run_plugin(self) -> None:
        """Run a plugin."""
        fakeplugin: pathlib.Path = self._base_dir / 'fakeplugin.py'
        fakeplugin.write_text(
                'import base64\n'\
                'import json\n'\
                'import sys\n'\
                'print('\
                'json.loads(base64.b64decode(sys.argv[1]).decode())["file"])',
                encoding='utf-8')
        self.assertEqual(
                self._upset.run_task(
                    self._task,
                    self._base_dir,
                    user='', host='', ssh_key=pathlib.Path(),
                    password=getpass.getpass(),
                    for_task={}),
                'a\nb\n')

if __name__ == '__main__':
    unittest.main()
