#!/usr/bin/env python3.10
"""Upset."""

import argparse
import logging
import pathlib
import sys

from types import Any, ModuleType

import pkg_resources

logger: logging.Logger = logging.getLogger(__name__)

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
    logging_handler: logging.StreamHandler = logging.StreamHandler()
    logging_handler.setLevel(logging.DEBUG)
    logging_formatter = logging.Formatter('%(levelname)s %(name)s %(message)s')
    logging_handler.setFormatter(logging_formatter)
    root_logger: logging.Logger = logging.getLogger()
    root_logger.setLevel(logging.ERROR)
    root_logger.addHandler(logging_handler)
    root_logger.setLevel(levels[verbosity_level])


if __name__ == '__main__':
    main()
