#!/usr/bin/env python3.10
"""Upset."""

import argparse
import importlib
import logging
import pathlib
import sys

from types import Any, ModuleType

import pkg_resources

logger: logging.Logger = logging.getLogger()

class Upset:
    """
    Attributes:
        _plugins: TEXT
    """

    def __init__(self) -> None:
        """Initialise class attributes."""




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


if __name__ == '__main__':
    main()
