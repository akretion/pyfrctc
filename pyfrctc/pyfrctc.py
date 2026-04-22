# Copyright 2026 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# Licence LGPL-2.1 or later (https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html).

import logging
from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import BackendApplicationClient
from stdnum.fr.siren import is_valid as siren_is_valid
from stdnum.fr.siret import is_valid as siret_is_valid
import json
import importlib
from io import BytesIO

VERSION = importlib.metadata.version("pyfrctc")
FORMAT = '%(asctime)s [%(levelname)s] %(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger('pyfrctc')
logger.setLevel(logging.INFO)

PLATFORM2TOKEN_URL = {
    'superpdp': 'https://api.superpdp.tech/oauth2/token',
    }
PLATFORM2BASE_URL = {
    'superpdp': 'https://api.superpdp.tech',
    }
AFNOR_API_VERSION = 'v1'
LIMIT = 100  # 100 is the max value for multi-page requests
TIMEOUT = 30


def get_session(client_id, client_secret, platform="superpdp"):
    if platform not in PLATFORM2TOKEN_URL:
        raise ValueError(f"Platform {platform} is not supported yet.")
    if not client_id:
        raise ValueError("Missing value for client_id argument")
    if not isinstance(client_id, str):
        raise ValueError("Argument client_id must be a string")
    if not client_secret:
        raise ValueError("Missing value for client_secret argument")
    if not isinstance(client_secret, str):
        raise ValueError("Argument client_secret must be a string")
    logger.debug(f'get_session called for platform {platform}')
    token_url = PLATFORM2TOKEN_URL[platform]

    def save_token(token):
        logger.info('New token saved')

    logger.info(f'Connecting on {token_url} (v{VERSION})')
    client = BackendApplicationClient(client_id=client_id)
    oauth = OAuth2Session(client=client)
    try:
        token = oauth.fetch_token(
            token_url=token_url, client_id=client_id, client_secret=client_secret, timeout=TIMEOUT)
    except Exception as e:
        raise ConnectionError(f"Query on {token_url} failed. Error: {str(e)}")
    extra = {"client_id": client_id, "client_secret": client_secret}
    session = OAuth2Session(
        client_id,
        token=token,
        auto_refresh_url=token_url,
        auto_refresh_kwargs=extra,
        token_updater=save_token)
    return session


def _get_plateform(session):
    if not session:
        raise ValueError("session argument has no value")
    for plateform, token_url in PLATFORM2TOKEN_URL.items():
        if token_url == session.auto_refresh_url:
            return plateform
    logger.warning(f"token_url {token_url} is not in PLATFORM2TOKEN_URL. It should never happen.")
    return None


def healthcheck(session, raise_if_error=True, type="directory"):
    if not session:
        raise ValueError("session argument has no value")
    if type not in ('directory', 'flow'):
        raise ValueError("type argument can have 2 values: 'directory' or 'flow'")
    platform = _get_plateform(session)
    if platform not in PLATFORM2BASE_URL:
        raise ValueError(f"Platform {platform} is not supported yet.")
    url = f"{PLATFORM2BASE_URL[platform]}/afnor-{type}/{AFNOR_API_VERSION}/healthcheck"
    logger.info(f'Sending GET request on {url} (v{VERSION})')
    try:
        get_res = session.get(url, timeout=TIMEOUT)
    except Exception as e:
        logger.warning(f'GET request on {url} failed. Error: {str(e)}')
        if raise_if_error:
            raise ConnectionError(f"GET request on {url} failed. Error: {str(e)}")
        return False
    status_code = get_res.status_code
    if status_code == 200:
        return True
    else:
        logger.warning(f'GET request on {url} returned HTTP error {status_code}')
        if raise_if_error:
            raise ConnectionError(f"GET request on {url} returned HTTP error {status_code}.")
        return False


def get_directory_siren(session, siren):
    """Returns False if SIREN is not in the directory"""
    if not session:
        raise ValueError("session argument has no value")
    platform = _get_plateform(session)
    if platform not in PLATFORM2BASE_URL:
        raise ValueError(f"Plateform {platform} is not supported yet.")
    if not siren:
        raise ValueError("siren argument has no value")
    if not isinstance(siren, str):
        raise ValueError("siren argument must be a string")
    siren = "".join(x for x in siren if not x.isspace())
    if not siren_is_valid(siren):
        raise ValueError(f"SIREN '{siren}' is not valid.")
    url = f"{PLATFORM2BASE_URL[platform]}/afnor-directory/{AFNOR_API_VERSION}/siren/code-insee:{siren}"
    logger.info(f"Sending GET request on {url} (v{VERSION})")
    try:
        get_res = session.get(url, timeout=TIMEOUT)
    except Exception as e:
        raise ConnectionError(f"GET request on {url} failed. Error: {str(e)}")
    status_code = get_res.status_code
    if status_code == 404:  # SIREN not in directory
        return False
    elif status_code == 200:
        siren_dict = get_res.json()
        logger.debug(f'Answer JSON: {siren_dict}')
        answer_siren = siren_dict.get('siren')
        if answer_siren != siren:
            raise RuntimeError(f"Answer of GET request on {url} is inconsistent: SIREN in answer ({answer_siren}) is different from query SIREN ({siren}). This should never happen.")
        return siren_dict
    else:
        error_code = error_msg = None
        try:
            error_json = get_res.json()
            error_code = error_json.get('errorCode')
            error_msg = error_json.get('errorMessage')
        except Exception:
            pass
        raise RuntimeError(f"GET request on {url} failed ({status_code}). Error code: {error_code}. Error message: {error_msg}")


def get_directory_siren_parsed(session, siren):
    siren_dict = get_directory_siren(session, siren)
    if siren_dict:
        closed = siren_dict.get('administrativeStatus') == 'C'
        entity_type = "no"
        if siren_dict.get('entityType'):
            entity_type_map = {
                'PrivateVatRegistered': 'private',
                'Public': 'public',
                }
            entity_type = entity_type_map[siren_dict['entityType']]
        res = {
            "name": siren_dict.get('businessName'),
            "closed": closed,
            "entity_type": entity_type,
            "siren": siren_dict['siren'],
            }
    else:
        siren = "".join(x for x in siren if not x.isspace())
        res = {
            'entity_type': 'no',
            'siren': siren,
            }
    return res


def get_directory_siret(session, siret):
    if not session:
        raise ValueError("session argument has no value")
    platform = _get_plateform(session)
    if platform not in PLATFORM2BASE_URL:
        raise ValueError(f"Plateform {platform} is not supported yet.")
    if not siret:
        raise ValueError("siret argument has no value")
    if not isinstance(siret, str):
        raise ValueError("siret argument must be a string")
    siret = "".join(x for x in siret if not x.isspace())
    if not siret_is_valid(siret):
        raise ValueError(f"SIRET '{siret}' is not valid.")
    url = f"{PLATFORM2BASE_URL[platform]}/afnor-directory/{AFNOR_API_VERSION}/siret/code-insee:{siret}"
    logger.info(f"Sending GET request on {url} (v{VERSION})")
    try:
        get_res = session.get(url, timeout=TIMEOUT)
    except Exception as e:
        raise ConnectionError(f"GET request on {url} failed. Error: {str(e)}")
    status_code = get_res.status_code
    if status_code != 200:
        error_code = error_msg = None
        try:
            error_json = get_res.json()
            error_code = error_json.get('errorCode')
            error_msg = error_json.get('errorMessage')
        except Exception:
            pass
        raise RuntimeError(f"GET request on {url} failed ({status_code}). Error code: {error_code}. Error message: {error_msg}.")
    siret_dict = get_res.json()
    logger.debug(f'Answer JSON: {siret_dict}')
    answer_siret = siret_dict.get('siret')
    if answer_siret != siret:
        raise RuntimeError(f"Answer of GET request on {url} is inconsistent: SIRET in answer ({answer_siret}) is different from query SIRET ({siret}). This should never happen.")
    return siret_dict


def get_directory_siret_parsed(session, siret):
    siret_dict = get_directory_siret(session, siret)
    closed = siret_dict.get('administrativeStatus') == 'C'
    res = {
        "name": siret_dict.get('name'),
        "closed": closed,
        "country_code": siret_dict.get('address', {}).get('countryCode'),
        "zip": siret_dict.get('address', {}).get('postalCode'),
        "street": siret_dict.get('address', {}).get('addressLine1'),
        "city": siret_dict.get('address', {}).get('locality'),
        "siret": siret_dict['siret'],
        }
    # Reminder: a public entity without service nor commitment required doesn't have a
    # key 'b2gAdditionalData' in JSON answer
    if 'b2gAdditionalData' in siret_dict and isinstance(siret_dict['b2gAdditionalData'], dict):
        res.update({
            'b2g_service_required': siret_dict['b2gAdditionalData'].get('serviceCodeStatus'),
            'b2g_commitment_required': siret_dict['b2gAdditionalData'].get('managesLegalCommitmentCode'),
            'b2g_service_or_commitment_required': siret_dict['b2gAdditionalData'].get('managesLegalCommitmentOrServiceCode'),
        })
    return res


def get_directory_lines(session, siren_or_siret):
    if not session:
        raise ValueError("session argument has no value")
    platform = _get_plateform(session)
    if platform not in PLATFORM2BASE_URL:
        raise ValueError(f"Plateform {platform} is not supported yet.")
    if not siren_or_siret:
        raise ValueError("siren_or_siret argument has no value")
    if not isinstance(siren_or_siret, str):
        raise ValueError("siren_or_siret argument must be a string")
    # remove un-useful chars
    siren_or_siret = "".join(x for x in siren_or_siret if not x.isspace())
    siren = siret = False
    if len(siren_or_siret) == 9:
        if not siren_is_valid(siren_or_siret):
            raise ValueError(f"SIREN '{siren_or_siret}' is not valid.")
        siren = siren_or_siret
    elif len(siren_or_siret) == 14:
        if not siret_is_valid(siren_or_siret):
            raise ValueError("SIRET '{siren_or_siret}' is not valid.")
        siret = siren_or_siret
        siren = siren_or_siret[:9]
    else:
        raise ValueError("'{siren_or_siret}' is not a valid SIREN nor SIRET.")

    res = {}  # key = dir line identifier, value = dir line values
    query_json = {
        "filters": {
            "siren": {"op": "strict", "value": siren},
        },
        "limit": LIMIT,
        "ignore": 0,  # for multipage
        "sorting": [{
            'field': "addressingIdentifier", "sortingOrder": "ascending",
            }],
        }
    if siret:
        query_json['filters']["siret"] = {"op": "strict", "value": siret}
    url = f"{PLATFORM2BASE_URL[platform]}/afnor-directory/{AFNOR_API_VERSION}/directory-line/search"
    logger.info(f"Sending POST request on {url} (v{VERSION})")
    logger.debug(f"Json in query: {query_json}")
    try:
        post_res = session.post(url, json=query_json, timeout=TIMEOUT)
    except Exception as e:
        raise ConnectionError(f"POST request on {url} failed. Error: {str(e)}")
    status_code = post_res.status_code
    if status_code not in (200, 204, 206):
        error_code = error_msg = None
        try:
            error_json = post_res.json()
            error_code = error_json.get('errorCode')
            error_msg = error_json.get('errorMessage')
        except Exception:
            pass
        raise RuntimeError(f"POST request on {url} failed ({status_code}). Error code: {error_code}. Error message: {error_msg}.")
    elif status_code == 204:
        logger.warning("POST request on {url} returned HTTP code 204, which means there is no directory lines.")
        return res
    elif status_code == 206:
        raise RuntimeError(f"POST request on {url} returned HTTP code 206. It should never happen because we set the limit to {LIMIT}, which is <= to the minimum value that must be supported by all platforms (100).")
    list_dir_dict = post_res.json()
    logger.debug(f"Answer JSON: {list_dir_dict}")
    if "results" in list_dir_dict and isinstance(list_dir_dict['results'], list) and 'totalNumberOfResults' in list_dir_dict and isinstance(list_dir_dict['totalNumberOfResults'], int):
        for dir_line in list_dir_dict['results']:
            res[dir_line['addressingIdentifier']] = dir_line
        result_total = list_dir_dict['totalNumberOfResults']
    else:
        raise RuntimeError(f"Answer to POST request on {url} is malformed.")
    if result_total > LIMIT:
        req_count = 2
        current_result_count = LIMIT
        while current_result_count < result_total:
            query_json["ignore"] = current_result_count
            try:
                post_res = session.post(url, json=query_json, timeout=TIMEOUT)
            except Exception as e:
                logger.warning(f'POST request on {url} failed. Error: {str(e)}')
                raise ConnectionError(f"POST request number {req_count} on {url} failed. Error: {str(e)}")
            status_code = post_res.status_code
            if status_code not in (200, 204, 206):
                raise ConnectionError(f"POST request number {req_count} on {url} returned error code {status_code}.")

            elif status_code == 204:
                # this should not happen in a second+ iteration
                raise Exception("POST request number {req_count} on {url} returned HTTP code 204. It should not happen on a 'next page' iteration.")

            elif status_code == 206:
                raise Exception("POST request number {req_count}  on {url} returned HTTP code 206. It should never happen because we set the limit to {LIMIT}, which is <= to the minimum value that must be supported by all platforms (100).")
            list_dir_dict = post_res.json()
            logger.debug(f"Answer JSON: {list_dir_dict}")
            if "results" in list_dir_dict and isinstance(list_dir_dict['results'], list) and 'totalNumberOfResults' in list_dir_dict and isinstance(list_dir_dict['totalNumberOfResults'], int):
                for dir_line in list_dir_dict['results']:
                    res[dir_line['addressingIdentifier']] = dir_line
                cur_result_total = list_dir_dict['totalNumberOfResults']
                if cur_result_total != result_total:
                    raise Exception("Answer to request number {req_count} on {url} returned a totalNumberOfResults of {cur_result_total} which is different from the value of the first request ({result_total}). This should never happen.")
            else:
                raise Exception(f"Answer to POST request number {req_count} on {url} is malformed.")
            current_result_count += LIMIT
            req_count += 1
    if len(res) != result_total:
        raise Exception(f"The number of directory lines ({len(res)}) is different from the total number of results announced by the API ({result_total}). This should never happen.")
    logger.info(f'Returning {len(res)} directory lines')
    return res


def get_directory_lines_parsed(session, siren_or_siret, siret_parsed=None, filter_out_factures_publiques=True):
    if siret_parsed is None:
        siret_parsed = {}
    identifier2vals = get_directory_lines(session, siren_or_siret)
    siren_or_siret = "".join(x for x in siren_or_siret if not x.isspace())
    if len(siren_or_siret) == 9:
        siren = siren_or_siret
        siret = False
    elif len(siren_or_siret) == 14:
        siren = siren_or_siret[:9]
        siret = siren_or_siret
    if siret_parsed:
        if not siret:
            raise RuntimeError("If siret_parsed arg has a value, siren_or_siret should be a SIRET")
        if siret_parsed.get('siret') != siret:
            raise RuntimeError(f"'siret' in siret_parsed (siret_parsed.get('siret')) should be identical to siret given in siren_or_siret arg ({siren_or_siret})")

    res = {}
    for identifier, vals in identifier2vals.items():
        routing_code = routing_code_name = suffix = False
        commitment_required = False
        dir_siren = vals.get('siren')
        if not dir_siren:
            raise RuntimeError("A siren key should be present")
        if siren != dir_siren:
            raise RuntimeError("SIREN in directory line value must be the same as SIREN given as argument")
        dir_siret = vals.get('siret')
        if dir_siret:
            if len(dir_siret) != 14:
                raise RuntimeError("SIRET in directory line '{identifier}' should have 14 caracters")
            if not siret_is_valid(dir_siret):
                raise RuntimeError("SIRET '{dir_siret}' in directory line '{identifier}' is invalid")
            if siret and siret != dir_siret:
                raise RuntimeError("SIRET in directory line value must be the same as SIRET given as argument")
        if "routingCode" in vals:
            type = "routing_code"
            routing_dict = vals['routingCode']
            if not isinstance(routing_dict, dict):
                raise RuntimeError(f"routingCode must be a dict in directory line '{identifier}'")
            if not dir_siret:
                raise RuntimeError("SIRET is not provided in routing directory line '{identifier}'")
            if "addressingSuffix" in vals:
                raise RuntimeError("Key 'addressingSuffix' should not be present in routing directory line '{identifier}'")
            routing_code = routing_dict.get("routingIdentifier")
            if not routing_code:
                raise RuntimeError(f"Missing 'routingIdentifier' in directory line {identifier}")
            if not isinstance(routing_code, str):
                raise RuntimeError(f"routingIdentifier must be a string in directory line {identifier}")
            if filter_out_factures_publiques and routing_code == "FACTURES_PUBLIQUES":
                continue
            routing_code_name = routing_dict.get("routingCodeName")
            if not routing_code_name:
                raise RuntimeError(f"Missing 'routingCodeName' in directory line {identifier}")
            if not isinstance(routing_code_name, str):
                raise RuntimeError(f"routingCodeName must be a string in directory line {identifier}")
            routing_id_type = routing_dict.get("routingIdentifierType")
            if routing_id_type != "0224":
                raise RuntimeError(f"routingIdentifierType has value {routing_id_type} in directory line '{identifier}' (expected value is '0224')")
            commitment_required = routing_dict.get('managesLegalCommitmentCode', False)
            if not isinstance(commitment_required, bool):
                raise RuntimeError(f"managesLegalCommitmentCode must be a boolean in directory line '{identifier}'")
            if siret_parsed.get('b2g_commitment_required') and not commitment_required:
                logger.warning(f"This public entity has global property commitment_required, but the directory line '{identifier}' is not marked as commitment_required")
                commitment_required = True
            expected_identifier = f"{siren}_{siret}_{routing_code}"

        elif "addressingSuffix" in vals:
            type = "suffix"
            suffix = vals['addressingSuffix']
            if not isinstance(suffix, str):
                raise RuntimeError("Value of 'addressingSuffix' must be a string")
            if dir_siret:
                raise RuntimeError("SIRET should not be present on a directory line type suffix")
            expected_identifier = f"{siren}_{suffix}"
        elif dir_siret:
            type = "siret"
            expected_identifier = f"{siren}_{siret}"
        else:
            type = "siren"
            expected_identifier = siren
        if expected_identifier != identifier:
            raise RuntimeError(f"Directory line '{identifier}' type {type} was expected to be '{expected_identifier}'")
        state_map = {
            'Upcoming': 'upcoming',
            'Enabled': 'active',
            'Disabled': 'disabled',
            }
        dir_state = vals.get('directoryLineStatus')
        if dir_state:
            if dir_state not in state_map:
                raise RuntimeError(f"Directory line '{identifier}' has directoryLineStatus '{dir_state}'. This value is not expected.")
            state = state_map[dir_state]
        else:
            state = 'disabled'
        if siret_parsed and type == 'siret':
            if siret_parsed.get('b2g_service_or_commitment_required'):
                logger.info(f"Setting commitment_required on directory line identifier '{identifier}' because the public entity has b2g_service_or_commitment_required")
                commitment_required = True
            if siret_parsed.get('b2g_service_required'):
                logger.info(f"Setting directory line identifier '{identifier}' to disabled because the public entity has service required")
                state = 'disabled'

        new_vals = {
            'type': type,
            'siren': siren,
            'siret': dir_siret,
            "suffix": suffix,
            "routing_code": routing_code,
            "routing_code_name": routing_code_name,
            "commitment_required": commitment_required,
            'state': state,
            }
        res[identifier] = new_vals
    return res


def send_flow(session, file_bin, filename, flow_syntax, processing_rule):
    if not session:
        raise ValueError("session argument has no value")
    if not file_bin:
        raise ValueError("file_bin argument has no value")
    if not isinstance(file_bin, bytes):
        raise ValueError("file_bin argument must be a bytes")
    if not filename:
        raise ValueError("filename argument has no value")
    if not isinstance(filename, str):
        raise ValueError("filename argument must be a string")
    if len(filename) > 255:
        raise ValueError(f"filename length is {len(filename)}, which is over the maxium (255)")
    if flow_syntax not in ('CII', 'UBL', 'Factur-X', 'CDAR', 'FRR'):
        raise ValueError("flow_syntax argument has a wrong value")
    if processing_rule not in ('B2B', 'B2BInt', 'B2C', 'B2G', 'B2GInt', 'OutOfScope', 'B2GOutOfScope', 'ArchiveOnly', 'NotApplicable'):
        raise ValueError("processing_rule argument has a wrong value")
    platform = _get_plateform(session)
    if platform not in PLATFORM2BASE_URL:
        raise ValueError(f"Plateform {platform} is not supported yet.")
    payload = {
        'file': (filename, BytesIO(file_bin)),
        'flowInfo': (None, json.dumps({
            'flowSyntax': flow_syntax,
            'name': filename,
            # 'processingRule': processing_rule,  # not yet supported by SuperPDP
            }), 'text/plain'),
        }
    url = f"{PLATFORM2BASE_URL[platform]}/afnor-flow/{AFNOR_API_VERSION}/flows"
    logger.info(f"Sending POST request on {url} (v{VERSION})")
    try:
        post_res = session.post(url, files=payload, timeout=TIMEOUT)
    except Exception as e:
        raise ConnectionError(f"POST request on {url} failed. Error: {str(e)}")
    status_code = post_res.status_code
    if status_code != 202:
        error_code = error_msg = None
        try:
            error_json = post_res.json()
            error_code = error_json.get('errorCode')
            error_msg = error_json.get('errorMessage')
        except Exception:
            pass
        raise RuntimeError(f"POST request on {url} failed ({status_code}). Error code: {error_code}. Error message: {error_msg}")
    flows_dict = post_res.json()
    logger.debug(f"Answer JSON: {flows_dict}")
    # We could check that the value received == value sent for processingRule and name
    answer_flow_syntax = flows_dict.get('flowSyntax')
    if answer_flow_syntax and answer_flow_syntax != flow_syntax:
        raise RuntimeError(f"Query had flowSyntax={flow_syntax} but answer has flowSyntax={answer_flow_syntax}")
    return flows_dict


def search_flows(session, updated_after, flow_direction, flow_type, updated_before=None):
    # TODO implement multi-page
    # Pagination works with the updatedAfter property
    # The comparison with current date is strict : updatedAt > updatedAfter
    if not session:
        raise ValueError("session argument has no value")
    if not updated_after:
        raise ValueError("updated_after argument must have a value")
    # TODO add check for updated_after ?
    if flow_direction:
        if isinstance(flow_direction, str):
            flow_direction = [flow_direction]
        flow_direction_values = ['In', 'Out']
        if isinstance(flow_direction, list):
            for flow_dir_value in flow_direction:
                if flow_dir_value not in flow_direction_values:
                    raise ValueError(f"Value {flow_dir_value} is not allowed for the argument flow_direction. Allowed values: {flow_direction_values}")
        else:
            raise ValueError("Argument flow_direction must be a list of stings (or a string)")
    if flow_type:
        if isinstance(flow_type, str):
            flow_type = [flow_type]
        flow_type_values = [
            'CustomerInvoice', 'SupplierInvoice',
            'StateInvoice',
            'CustomerInvoiceLC', 'SupplierInvoiceLC']  # LC = Life Cycle
        if isinstance(flow_type, list):
            for flow_type_value in flow_type:
                if flow_type_value not in flow_type_values:
                    raise ValueError(f"Value {flow_type_value} is not allowed for the argument flow_type. Allowed values: {flow_type_values}")
        else:
            raise ValueError("Argument flow_type must be a list of strings (or a string)")
    platform = _get_plateform(session)
    if platform not in PLATFORM2BASE_URL:
        raise ValueError(f"Plateform {platform} is not supported yet.")
    query_json = {
        "where": {
            "updatedAfter": updated_after,
            },
        "limit": LIMIT,
        }
    if flow_type:
        query_json["where"]["flowType"] = flow_type
    if flow_direction:
        query_json["where"]["flowDirection"] = flow_direction
    url = f"{PLATFORM2BASE_URL[platform]}/afnor-flow/{AFNOR_API_VERSION}/flows/search"
    logger.info(f"Sending POST request on {url} (v{VERSION})")
    try:
        post_res = session.post(url, json=query_json, timeout=TIMEOUT)
    except Exception as e:
        raise ConnectionError(f"POST request on {url} failed. Error: {str(e)}")
    status_code = post_res.status_code
    if status_code != 200:
        error_code = error_msg = None
        try:
            error_json = post_res.json()
            error_code = error_json.get('errorCode')
            error_msg = error_json.get('errorMessage')
        except Exception:
            pass
        raise RuntimeError(f"POST request on {url} failed ({status_code}). Error code: {error_code}. Error message: {error_msg}")
    flows_dict = post_res.json()
    logger.debug(f'Answer JSON: {flows_dict}')
    return flows_dict


def get_flow(session, flow_id, doc_type=None):
    """
    If doc_type is None or 'Metadata', it returns a dict
    Otherwise, returns a file as bytes object
    """
    if not session:
        raise ValueError("session argument has no value")
    if not flow_id:
        raise ValueError("flow_id argument has no value")
    if not isinstance(flow_id, str):
        raise ValueError("flow_id argument must be a string")
    if doc_type is not None:
        doc_type_values = ('Metadata', 'Original', 'Converted', 'ReadableView')
        if doc_type not in doc_type_values:
            raise ValueError(f"Value {doc_type} is not allowed for the argument doc_type. Allowed values: {doc_type_values}")
    platform = _get_plateform(session)
    if platform not in PLATFORM2BASE_URL:
        raise ValueError(f"Plateform {platform} is not supported yet.")
    url = f"{PLATFORM2BASE_URL[platform]}/afnor-flow/{AFNOR_API_VERSION}/flows/{flow_id}"
    params = {}
    if doc_type:
        params['docType'] = doc_type
    logger.info(f'Sending GET request on {url} with params {params} (v{VERSION})')
    try:
        get_res = session.get(url, params=params, timeout=TIMEOUT)
    except Exception as e:
        raise ConnectionError(f"GET request on {url} failed. Error: {str(e)}")
    status_code = get_res.status_code
    if status_code != 200:
        error_code = error_msg = None
        try:
            error_json = get_res.json()
            error_code = error_json.get('errorCode')
            error_msg = error_json.get('errorMessage')
        except Exception:
            pass
        raise RuntimeError(f"GET request on {url} failed ({status_code}). Error code: {error_code}. Error message: {error_msg}")
    if not doc_type or doc_type == 'Metadata':  # Metadata is the default
        metadata_dict = get_res.json()
        logger.debug(f'Answer JSON: {metadata_dict}')
        return metadata_dict
    file_bin = get_res.content
    if not file_bin:
        raise RuntimeError(f"Empty file retrieved from {url}")
    if not isinstance(file_bin, bytes):
        raise RuntimeError(f"File retrieved from {url} is not a python bytes object")
    return file_bin
