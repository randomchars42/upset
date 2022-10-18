"""Test Upset."""

import logging
import logging.config
import pathlib
import unittest

from typing import Any
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

# pylint: disable=too-many-public-methods
class TestUpsetUpset(unittest.TestCase):
    """Test Upset from upset."""

    def setUp(self) -> None:
        """Add test directory and instantiate class."""
        self._upset: upset.Upset = upset.Upset()
        self._base_dir: pathlib.Path = pathlib.Path('tests/tmp')
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
        plan: pathlib.Path = pathlib.Path(self._base_dir / 'plan')
        plan.write_text('[{"name": "a", "plugin": "c"},{"name": "b"}]',
                encoding='utf-8')
        tasklist: list[Any] = self._upset.read_plan(plan)
        self.assertTrue(len(tasklist) == 2)
        self.assertTrue(tasklist[0].name == 'a')
        self.assertTrue(tasklist[0].plugin == 'c')
        self.assertTrue(tasklist[1].name == 'b')

    def test_read_plan_fail_missing(self) -> None:
        """Fail because of missing / inaccessible plan."""
        plan: pathlib.Path = pathlib.Path(self._base_dir / 'plan')
        with self.assertRaises(upset.UpsetError):
            self._upset.read_plan(plan)

    def test_read_plan_fail_json(self) -> None:
        """Fail because of misshapen JSON."""
        plan: pathlib.Path = pathlib.Path(self._base_dir / 'plan')
        plan.write_text('[{"name": "a",{"name": "b"}]', encoding='utf-8')
        with self.assertRaises(upset.UpsetError):
            self._upset.read_plan(plan)

    def test_build_sudo_command(self) -> None:
        """Build sudo command sequence."""
        self.assertEqual(
                self._upset.build_sudo_command(['echo', '"Hello"'], 'password'),
                ['echo ZWNobyAicGFzc3dvcmQiIHwgc3VkbyAtUyAtLXByb21wdD0gLS0gZWNobyAiSGVsbG8i | base64 -d | $SHELL'])

