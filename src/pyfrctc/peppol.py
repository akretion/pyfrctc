# Copyright 2026 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# Licence LGPL-2.1 or later (https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html).

import base64
import hashlib
import logging
from urllib.parse import urlparse

import dns.resolver  # pip install dnspython

logger = logging.getLogger("pyfrctc")


def check_directory_line_peppol_status(dir_line):
    if not isinstance(dir_line, str):
        raise ValueError("The dir_line argument must be a string")
    dir_line = dir_line.strip()
    logger.info(f"Checking PEPPOL status of directory line {dir_line}")
    dir_line_w_prefix = f"0225:{dir_line.lower()}"
    sha256_hash = hashlib.sha256(dir_line_w_prefix.encode("utf-8")).digest()
    base32_hash = base64.b32encode(sha256_hash).decode("utf-8").rstrip("=")
    base32_hash_lower = base32_hash.lower()
    dns_to_query = (
        f"{base32_hash_lower}.iso6523-actorid-upis.participant.sml.prod.tech.peppol.org"
    )
    logger.info(f"Sending NAPTR DNS {dns_to_query}")
    try:
        answers = dns.resolver.resolve(dns_to_query, "NAPTR")
        logger.info(f"{len(answers)} answers received for the DNS query")
        for answer in answers:
            logger.info(f"DNS answer: {answer}")
            regexp = answer.regexp.decode("utf-8")
            logger.debug(f"Regexp part of DNS answer: {regexp}")
            if "!" in regexp:
                regexp_split = regexp.split("!")
                if len(regexp_split) >= 3:
                    peppol_url = regexp_split[2]
                    logger.debug(f"PEPPOL URL: {peppol_url}")
                    parsed_peppol_url = urlparse(peppol_url)
                    ap_dns = parsed_peppol_url.netloc
                    logger.info(
                        f"Dir line {dir_line} is active in PEPPOL and "
                        f"handled by AP {ap_dns}"
                    )
                    return ap_dns
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        # DNS query successfully executed... but no answer
        logger.error(f"No PEPPOL DNS entry for directory line {dir_line}")
        return False
    except Exception as err:
        msg = f"DNS query could not be executed. Error: {err}"
        logger.error(msg)
        raise ValueError(msg) from err
    logger.warning(
        "Failed to parse the result of the DNS queries. This should never happen."
    )
    return False
