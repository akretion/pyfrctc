#! /usr/bin/env python
# Copyright 2026 Alexis de Lattre <alexis.delattre@akretion.com>

import argparse
import logging
import sys

from pyfrctc import __version__ as pyctcversion
from pyfrctc import check_directory_line_peppol_status, configure_script_logging

__author__ = "Alexis de Lattre <alexis.delattre@akretion.com>"
__date__ = "September 2026"
__version__ = "0.1"


logger = logging.getLogger("pyfrctc")


def check_peppol_status(args):
    logger.info(
        f"peppol_dir_line_check version {__version__} "
        f"using pyfrctc lib version {pyctcversion}"
    )

    try:
        check_directory_line_peppol_status(args.dir_line)
    except Exception:
        # error has already been logged
        sys.exit(1)


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    usage = "pyfrctc-peppol_dir_line_check <directory_line>"
    epilog = f"Author: {__author__} - Version: {__version__}"
    description = (
        "This script checks the PEPPOL status of a French e-Invoicing directory line."
    )
    parser = argparse.ArgumentParser(
        usage=usage, epilog=epilog, description=description
    )
    parser.add_argument(
        "-l",
        "--log-level",
        dest="log_level",
        choices=["debug", "info", "warn", "error"],
        default="info",
        help="Set log level. Default value: info.",
    )
    parser.add_argument("dir_line", help="French eInvoicing directory line")
    args = parser.parse_args()
    log_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warn": logging.WARN,
        "error": logging.ERROR,
    }
    configure_script_logging(level=log_map[args.log_level])
    check_peppol_status(args)


def run():
    if __name__ == "__main__":
        main()


run()
