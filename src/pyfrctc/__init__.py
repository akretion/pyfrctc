import logging

__version__ = "0.11"
from .pyfrctc import (
    authorization_code_first_token,
    check_cdar_schematron,
    check_cdar_xsd,
    generate_cdar,
    get_authorization_url,
    get_directory_lines,
    get_directory_lines_parsed,
    get_directory_siren,
    get_directory_siren_parsed,
    get_directory_siret,
    get_directory_siret_parsed,
    get_flow,
    get_flow_metadata_parsed,
    get_session,
    healthcheck,
    parse_cdar,
    parse_cdar_raw,
    search_flows,
    search_flows_parsed,
    send_flow,
    send_flow_parsed,
)

__all__ = [
    "authorization_code_first_token",
    "generate_cdar",
    "get_authorization_url",
    "get_directory_lines",
    "get_directory_lines_parsed",
    "get_directory_siren",
    "get_directory_siren_parsed",
    "get_directory_siret",
    "get_directory_siret_parsed",
    "get_flow",
    "get_flow_metadata_parsed",
    "get_session",
    "healthcheck",
    "parse_cdar",
    "parse_cdar_raw",
    "check_cdar_schematron",
    "check_cdar_xsd",
    "search_flows",
    "search_flows_parsed",
    "send_flow",
    "send_flow_parsed",
]


def configure_script_logging(level=logging.INFO):
    logger = logging.getLogger("pyfrctc")
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(level)
