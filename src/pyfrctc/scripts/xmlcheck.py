#! /usr/bin/env python
# Copyright 2017-2023 Alexis de Lattre <alexis.delattre@akretion.com>

import argparse
import logging
import sys
from os.path import isfile

from lxml import etree

from pyfrctc import __version__ as pyfrctcversion
from pyfrctc import (
    check_cdar_schematron,
    check_cdar_xsd,
    check_ereporting_schematron,
    check_ereporting_xsd,
    configure_script_logging,
)

__author__ = "Alexis de Lattre <alexis.delattre@akretion.com>"
__date__ = "September 2026"
__version__ = "0.1"


logger = logging.getLogger("pyfrctc")


def xmlcheck(args):
    logger.info(
        "xmlcheck version %s using pyfrctc lib version %s", __version__, pyfrctcversion
    )

    if not isfile(args.xml_file):
        logger.error("%s is not a filename", args.xml_file)
        sys.exit(1)
    with open(args.xml_file, "rb") as xml_file:
        xml_bytes = xml_file.read()
    try:
        xml_root = etree.fromstring(xml_bytes)
    except Exception as e:
        logger.error(f"File '{args.xml_file}' is not a valid XML file. Error: {str(e)}")
        sys.exit(1)
    if args.flavor == "cdar":
        file_type = "cdar"
    elif args.flavor == "ereporting":
        file_type = "ereporting"
    else:
        if xml_root.tag.endswith("CrossDomainAcknowledgementAndResponse"):
            file_type = "cdar"
            logger.info("This XML file is a CDAR file (life cycle)")
        elif xml_root.tag.endswith("Report"):
            logger.info("This XML file is an e-Reporting file")
            file_type = "ereporting"
        else:
            logger.error("This XML is not a CDAR (life cycle) nor e-Reporting file")
            sys.exit(1)

    if file_type == "cdar":
        try:
            check_cdar_xsd(xml_root)
        except Exception as e:
            logger.error(e)
            sys.exit(1)
        if not args.disable_schematron:
            try:
                check_cdar_schematron(xml_bytes, raise_if_http_error=True)
            except Exception as e:
                logger.error(e)
                sys.exit(1)
    elif file_type == "ereporting":
        try:
            check_ereporting_xsd(xml_bytes)
        except Exception as e:
            logger.error(e)
            sys.exit(1)
        if not args.disable_schematron:
            try:
                check_ereporting_schematron(xml_bytes, raise_if_http_error=True)
            except Exception as e:
                logger.error(e)
                sys.exit(1)


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    usage = "pyfrctc-xmlcheck <xml_file>"
    epilog = f"Author: {__author__} - Version: {__version__}"
    description = (
        "This script checks CDAR and e-Reporting files against the XML "
        "Schema Definition and Schematron."
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
    parser.add_argument(
        "-f",
        "--flavor",
        dest="flavor",
        choices=["autodetect", "cdar", "ereporting"],
        default="autodetect",
        help="Set XML flavor. Default value: autodetect.",
    )
    parser.add_argument(
        "-ns",
        "--no-schematron-check",
        dest="disable_schematron",
        action="store_true",
        help="Disable Schematron check.",
    )
    parser.add_argument("xml_file", help="CDAR or e-Reporting XML file to check")
    args = parser.parse_args()
    log_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warn": logging.WARN,
        "error": logging.ERROR,
    }
    configure_script_logging(level=log_map[args.log_level])
    xmlcheck(args)


def run():
    if __name__ == "__main__":
        main()


run()
