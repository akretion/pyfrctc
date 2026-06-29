# Copyright 2026 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# Licence LGPL-2.1 or later (https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html).

import base64
import datetime
import hashlib
import importlib.metadata
import importlib.resources
import json
import logging
import secrets
import time
from io import BytesIO
from urllib.parse import urlencode

import pytz
import saxonche
from lxml import etree, objectify
from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session
from stdnum.fr.siren import is_valid as siren_is_valid
from stdnum.fr.siret import is_valid as siret_is_valid

# from pprint import pprint

VERSION = importlib.metadata.version("pyfrctc")
FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(format=FORMAT)
logger = logging.getLogger("pyfrctc")
logger.setLevel(logging.INFO)

PLATFORMS = {
    "superpdp": {
        "afnor_base_url": "https://api.superpdp.tech",
        "token_url": "https://api.superpdp.tech/oauth2/token",
        "authorize_url": "https://api.superpdp.tech/oauth2/authorize",
        "label": "SUPER PDP",
    }
}
AFNOR_API_VERSION = "v1"
LIMIT = 100  # 100 is the max value for multi-page requests
TIMEOUT = 30
CDAR_XSD_FILE = "cdar-xsd/CrossDomainAcknowledgementAndResponse_100pD22B.xsd"
CDAR_XSL_FILE = "cdar-schematron/20260430_BR-FR-CDV-Schematron-CDAR_V1.3.1.xsl"
CDAR_NS_MAP = {
    "qdt": "urn:un:unece:uncefact:data:standard:QualifiedDataType:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
    "ram": "urn:un:unece:uncefact:data:standard:"
    "ReusableAggregateBusinessInformationEntity:100",
    "rsm": "urn:un:unece:uncefact:data:standard:"
    "CrossDomainAcknowledgementAndResponse:100",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}


def _get_plateform(session):
    if not session:
        raise ValueError("session argument has no value")
    token_url = session.auto_refresh_url
    for plateform, url_dict in PLATFORMS.items():
        if url_dict.get("token_url") == token_url:
            return plateform
    logger.warning(
        f"token_url {token_url} is not in PLATFORMS. It should never happen."
    )
    return None


def _get_session_client_credentials(
    platform,
    company_ident4log,
    get_token_method,
    update_token_method,
    client_id,
    client_secret,
):
    # In the client_credentials scenario, we can't use OAuth2Session()
    # to automate the retreival of a new access_token when the previous has expired
    # we have to code it ourselves !
    now_with_margin = time.time() + TIMEOUT
    token = get_token_method("client_credentials")
    use_existing_token = (
        token["access_token"]
        and token["expires_at"]
        and token["expires_at"] > now_with_margin
    )
    if use_existing_token:
        logger.info("Reuse an existing token for company %s", company_ident4log)
    else:
        logger.info("Must get a new token for company %s", company_ident4log)
        token = None
    # In OAuth2Session(), the argument auto_refresh_url=TOKEN_URL
    # is useless in this 'client_credentials' scenario,
    # but I use it because it is used by pyfrctc to get the plateform
    # from the session object (it avoids passing the plateform arg on every call to
    # pyfrctc for the AFNOR API
    client = BackendApplicationClient(client_id=client_id)
    session = OAuth2Session(
        client=client, token=token, auto_refresh_url=PLATFORMS[platform]["token_url"]
    )
    if not use_existing_token:
        token = session.fetch_token(
            PLATFORMS[platform]["token_url"],
            client_id=client_id,
            client_secret=client_secret,
            timeout=TIMEOUT,
            verify=True,
        )
        logger.info("Got a new token for company %s", company_ident4log)
        update_token_method(token)
    return session


def _get_session_authorization_code(
    platform, company_ident4log, get_token_method, update_token_method, client_id
):
    token = get_token_method("authorization_code")
    auto_refresh_kwargs = {"client_id": client_id}

    try:
        session = OAuth2Session(
            client_id,
            token=token,
            auto_refresh_url=PLATFORMS[platform]["token_url"],
            auto_refresh_kwargs=auto_refresh_kwargs,
            token_updater=update_token_method,
        )
    except Exception as e:
        raise RuntimeError(
            f"Failed to initiate a session with platform "
            f"'{PLATFORMS[platform]['label']}'. Error: {e}"
        ) from e

    return session


def get_session(
    platform,
    auth_method,
    company_ident4log,
    get_token_method,
    update_token_method,
    client_id,
    client_secret=None,
):
    if not platform:
        raise ValueError("Argument platform has no value")
    if not client_id:
        raise ValueError("Argument client_id has no value")
    if auth_method == "client_credentials":
        if not client_secret:
            raise ValueError(
                "Argument client_secret is required for auth_method "
                "'client_credentials'"
            )
        return _get_session_client_credentials(
            platform,
            company_ident4log,
            get_token_method,
            update_token_method,
            client_id,
            client_secret,
        )
    elif auth_method == "authorization_code":
        return _get_session_authorization_code(
            platform,
            company_ident4log,
            get_token_method,
            update_token_method,
            client_id,
        )
    else:
        raise ValueError(f"Wrong value for auth_method arg ({auth_method}).")


def get_authorization_url(platform, client_id, redirect_uri, optional_uri_params=None):
    if not platform:
        raise ValueError("Argument platform has no value")
    if platform not in PLATFORMS:
        raise ValueError(f"Platform {platform} is not supported")
    if not client_id:
        raise ValueError("Argument client_id has no value")
    if not redirect_uri:
        raise ValueError("Argument redirect_url has no value")
    if optional_uri_params is None:
        optional_uri_params = {}
    if not isinstance(optional_uri_params, dict):
        raise ValueError("Argument optional_uri_params must be a dict or None")
    authorize_url = PLATFORMS[platform]["authorize_url"]
    code_verifier = secrets.token_urlsafe(64)
    prep_code_challenge = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = (
        base64.urlsafe_b64encode(prep_code_challenge).decode("ascii").replace("=", "")
    )
    oauth = OAuth2Session(client_id, redirect_uri=redirect_uri, scope=[""])
    authorization_url, state_code = oauth.authorization_url(
        authorize_url,
        code_challenge=code_challenge,
        code_challenge_method="S256",
        **optional_uri_params,
    )
    return (authorization_url, state_code, code_verifier)


def authorization_code_first_token(
    platform,
    client_id,
    code_verifier,
    state,
    callback_code,
    redirect_uri,
    update_token_method,
):
    if not platform:
        raise ValueError("Argument platform has no value")
    if platform not in PLATFORMS:
        raise ValueError(f"Platform {platform} is not supported")
    if not client_id:
        raise ValueError("Argument client_id has no value")
    if not code_verifier:
        raise ValueError("Argument code_verifier has no value")
    if not state:
        raise ValueError("Argument state has no value")
    if not callback_code:
        raise ValueError("Argument callback_code has no value")
    if not redirect_uri:
        raise ValueError("Argument redirect_url has no value")
    token_url = PLATFORMS[platform]["token_url"]
    redirect_uri_params = {"code": callback_code, "scope": "", "state": state}
    authorization_response = f"{redirect_uri}?{urlencode(redirect_uri_params)}"
    oauth = OAuth2Session(client_id, redirect_uri=redirect_uri, scope=[""])
    token = oauth.fetch_token(
        token_url,
        authorization_response=authorization_response,
        code_verifier=code_verifier,
        timeout=TIMEOUT,
        verify=True,
    )
    if token:
        logger.info("Successfully got first refresh_token")
        update_token_method(token)
    else:
        raise RuntimeError("Failed to retreive first refresh token")


def healthcheck(session, raise_if_error=True, type="directory"):
    if not session:
        raise ValueError("session argument has no value")
    if type not in ("directory", "flow"):
        raise ValueError("type argument can have 2 values: 'directory' or 'flow'")
    platform = _get_plateform(session)
    if platform not in PLATFORMS:
        raise ValueError(f"Platform {platform} is not supported yet.")
    base_url = PLATFORMS[platform]["afnor_base_url"]
    url = f"{base_url}/afnor-{type}/{AFNOR_API_VERSION}/healthcheck"
    logger.info(f"Sending GET request on {url} (v{VERSION})")
    try:
        get_res = session.get(url, timeout=TIMEOUT)
    except Exception as e:
        logger.warning(f"GET request on {url} failed. Error: {str(e)}")
        if raise_if_error:
            raise ConnectionError(
                f"GET request on {url} failed. Error: {str(e)}"
            ) from e
        return False
    status_code = get_res.status_code
    if status_code == 200:
        return True
    else:
        logger.warning(f"GET request on {url} returned HTTP error {status_code}")
        if raise_if_error:
            raise ConnectionError(
                f"GET request on {url} returned HTTP error {status_code}."
            )
        return False


def get_directory_siren(session, siren):
    """Returns False if SIREN is not in the directory"""
    if not session:
        raise ValueError("session argument has no value")
    platform = _get_plateform(session)
    if platform not in PLATFORMS:
        raise ValueError(f"Plateform {platform} is not supported yet.")
    if not siren:
        raise ValueError("siren argument has no value")
    if not isinstance(siren, str):
        raise ValueError("siren argument must be a string")
    siren = "".join(x for x in siren if not x.isspace())
    if not siren_is_valid(siren):
        raise ValueError(f"SIREN {siren} is not valid.")
    base_url = PLATFORMS[platform]["afnor_base_url"]
    url = f"{base_url}/afnor-directory/" f"{AFNOR_API_VERSION}/siren/code-insee:{siren}"
    logger.info(f"Sending GET request on {url} (v{VERSION})")
    try:
        get_res = session.get(url, timeout=TIMEOUT)
    except Exception as e:
        raise ConnectionError(f"GET request on {url} failed. Error: {str(e)}") from e
    status_code = get_res.status_code
    if status_code == 404:  # SIREN not in directory
        return False
    elif status_code == 200:
        siren_dict = get_res.json()
        logger.debug(f"Answer JSON: {siren_dict}")
        answer_siren = siren_dict.get("siren")
        if answer_siren != siren:
            raise RuntimeError(
                f"Answer of GET request on {url} is inconsistent: "
                f"SIREN in answer ({answer_siren}) is different from "
                f"query SIREN ({siren}). This should never happen."
            )
        return siren_dict
    else:
        error_code = error_msg = None
        try:
            error_json = get_res.json()
            error_code = error_json.get("errorCode")
            error_msg = error_json.get("errorMessage")
        except Exception:
            pass
        raise RuntimeError(
            f"GET request on {url} failed ({status_code}). "
            f"Error code: {error_code}. Error message: {error_msg}"
        )


def get_directory_siren_parsed(session, siren):
    siren_dict = get_directory_siren(session, siren)
    if siren_dict:
        closed = siren_dict.get("administrativeStatus") == "C"
        entity_type = "no"
        if siren_dict.get("entityType"):
            entity_type_map = {
                "PrivateVatRegistered": "private",
                "Public": "public",
            }
            entity_type = entity_type_map[siren_dict["entityType"]]
        res = {
            "name": siren_dict.get("businessName"),
            "closed": closed,
            "entity_type": entity_type,
            "siren": siren_dict["siren"],
        }
    else:
        siren = "".join(x for x in siren if not x.isspace())
        res = {
            "entity_type": "no",
            "siren": siren,
        }
    return res


def get_directory_siret(session, siret):
    if not session:
        raise ValueError("session argument has no value")
    platform = _get_plateform(session)
    if platform not in PLATFORMS:
        raise ValueError(f"Plateform {platform} is not supported yet.")
    if not siret:
        raise ValueError("siret argument has no value")
    if not isinstance(siret, str):
        raise ValueError("siret argument must be a string")
    siret = "".join(x for x in siret if not x.isspace())
    if not siret_is_valid(siret):
        raise ValueError(f"SIRET {siret} is not valid.")
    base_url = PLATFORMS[platform]["afnor_base_url"]
    url = f"{base_url}/afnor-directory/" f"{AFNOR_API_VERSION}/siret/code-insee:{siret}"
    logger.info(f"Sending GET request on {url} (v{VERSION})")
    try:
        get_res = session.get(url, timeout=TIMEOUT)
    except Exception as e:
        raise ConnectionError(f"GET request on {url} failed. Error: {str(e)}") from e
    status_code = get_res.status_code
    if status_code != 200:
        error_code = error_msg = None
        try:
            error_json = get_res.json()
            error_code = error_json.get("errorCode")
            error_msg = error_json.get("errorMessage")
        except Exception:
            pass
        raise RuntimeError(
            f"GET request on {url} failed ({status_code}). "
            f"Error code: {error_code}. Error message: {error_msg}."
        )
    siret_dict = get_res.json()
    logger.debug(f"Answer JSON: {siret_dict}")
    answer_siret = siret_dict.get("siret")
    if answer_siret != siret:
        raise RuntimeError(
            f"Answer of GET request on {url} is inconsistent: "
            f"SIRET in answer ({answer_siret}) is different from "
            f"query SIRET ({siret}). This should never happen."
        )
    return siret_dict


def get_directory_siret_parsed(session, siret):
    siret_dict = get_directory_siret(session, siret)
    closed = siret_dict.get("administrativeStatus") == "C"
    res = {
        "name": siret_dict.get("name"),
        "closed": closed,
        "country_code": siret_dict.get("address", {}).get("countryCode"),
        "zip": siret_dict.get("address", {}).get("postalCode"),
        "street": siret_dict.get("address", {}).get("addressLine1"),
        "city": siret_dict.get("address", {}).get("locality"),
        "siret": siret_dict["siret"],
    }
    # Reminder: a public entity without service nor commitment required doesn't have a
    # key 'b2gAdditionalData' in JSON answer
    if "b2gAdditionalData" in siret_dict and isinstance(
        siret_dict["b2gAdditionalData"], dict
    ):
        res.update(
            {
                "b2g_service_required": siret_dict["b2gAdditionalData"].get(
                    "serviceCodeStatus"
                ),
                "b2g_commitment_required": siret_dict["b2gAdditionalData"].get(
                    "managesLegalCommitmentCode"
                ),
                "b2g_service_or_commitment_required": siret_dict[
                    "b2gAdditionalData"
                ].get("managesLegalCommitmentOrServiceCode"),
            }
        )
    return res


def get_directory_lines(session, siren_or_siret):
    if not session:
        raise ValueError("session argument has no value")
    platform = _get_plateform(session)
    if platform not in PLATFORMS:
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
            raise ValueError(f"SIREN {siren_or_siret} is not valid.")
        siren = siren_or_siret
    elif len(siren_or_siret) == 14:
        if not siret_is_valid(siren_or_siret):
            raise ValueError("SIRET {siren_or_siret} is not valid.")
        siret = siren_or_siret
        siren = siren_or_siret[:9]
    else:
        raise ValueError("{siren_or_siret} is not a valid SIREN nor SIRET.")

    res = {}  # key = dir line identifier, value = dir line values
    query_json = {
        "filters": {
            "siren": {"op": "strict", "value": siren},
        },
        "limit": LIMIT,
        "ignore": 0,  # for multipage
        "sorting": [
            {
                "field": "addressingIdentifier",
                "sortingOrder": "ascending",
            }
        ],
    }
    if siret:
        query_json["filters"]["siret"] = {"op": "strict", "value": siret}
    base_url = PLATFORMS[platform]["afnor_base_url"]
    url = f"{base_url}/afnor-directory/" f"{AFNOR_API_VERSION}/directory-line/search"
    logger.info(f"Sending POST request on {url} (v{VERSION})")
    logger.debug(f"Json in query: {query_json}")
    try:
        post_res = session.post(url, json=query_json, timeout=TIMEOUT)
    except Exception as e:
        raise ConnectionError(f"POST request on {url} failed. Error: {str(e)}") from e
    status_code = post_res.status_code
    if status_code not in (200, 204, 206):
        error_code = error_msg = None
        try:
            error_json = post_res.json()
            error_code = error_json.get("errorCode")
            error_msg = error_json.get("errorMessage")
        except Exception:
            pass
        raise RuntimeError(
            f"POST request on {url} failed ({status_code}). "
            f"Error code: {error_code}. Error message: {error_msg}."
        )
    elif status_code == 204:
        logger.warning(
            "POST request on {url} returned HTTP code 204, "
            "which means there is no directory lines."
        )
        return res
    elif status_code == 206:
        raise RuntimeError(
            f"POST request on {url} returned HTTP code 206. "
            f"It should never happen because we set the limit to {LIMIT}, "
            f"which is <= to the minimum value that must be supported by "
            "all platforms (100)."
        )
    list_dir_dict = post_res.json()
    logger.debug(f"Answer JSON: {list_dir_dict}")
    if (
        "results" in list_dir_dict
        and isinstance(list_dir_dict["results"], list)
        and "totalNumberOfResults" in list_dir_dict
        and isinstance(list_dir_dict["totalNumberOfResults"], int)
    ):
        for dir_line in list_dir_dict["results"]:
            res[dir_line["addressingIdentifier"]] = dir_line
        result_total = list_dir_dict["totalNumberOfResults"]
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
                logger.warning(f"POST request on {url} failed. Error: {str(e)}")
                raise ConnectionError(
                    f"POST request number {req_count} on {url} failed. "
                    f"Error: {str(e)}"
                ) from e
            status_code = post_res.status_code
            if status_code not in (200, 204, 206):
                raise ConnectionError(
                    f"POST request number {req_count} on {url} "
                    f"returned error code {status_code}."
                )

            elif status_code == 204:
                # this should not happen in a second+ iteration
                raise Exception(
                    f"POST request number {req_count} on {url} returned "
                    "HTTP code 204. It should not happen on a 'next page' iteration."
                )

            elif status_code == 206:
                raise Exception(
                    f"POST request number {req_count} on {url} returned "
                    "HTTP code 206. It should never happen because we set "
                    f"the limit to {LIMIT}, which is <= to the minimum value "
                    "that must be supported by all platforms (100)."
                )
            list_dir_dict = post_res.json()
            logger.debug(f"Answer JSON: {list_dir_dict}")
            if (
                "results" in list_dir_dict
                and isinstance(list_dir_dict["results"], list)
                and "totalNumberOfResults" in list_dir_dict
                and isinstance(list_dir_dict["totalNumberOfResults"], int)
            ):
                for dir_line in list_dir_dict["results"]:
                    res[dir_line["addressingIdentifier"]] = dir_line
                cur_result_total = list_dir_dict["totalNumberOfResults"]
                if cur_result_total != result_total:
                    raise Exception(
                        f"Answer to request number {req_count} on {url} "
                        f"returned a totalNumberOfResults of {cur_result_total} "
                        f"which is different from the value of the first "
                        f"request ({result_total}). This should never happen."
                    )
            else:
                raise Exception(
                    f"Answer to POST request number {req_count} on {url} is malformed."
                )
            current_result_count += LIMIT
            req_count += 1
    if len(res) != result_total:
        raise Exception(
            f"The number of directory lines ({len(res)}) is different "
            f"from the total number of results announced by the API "
            f"({result_total}). This should never happen."
        )
    logger.info(f"Returning {len(res)} directory lines")
    return res


def get_directory_lines_parsed(
    session, siren_or_siret, siret_parsed=None, filter_out_factures_publiques=True
):
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
            raise RuntimeError(
                "If siret_parsed arg has a value, siren_or_siret should be a SIRET"
            )
        if siret_parsed.get("siret") != siret:
            raise RuntimeError(
                f"'siret' in siret_parsed (siret_parsed.get('siret')) "
                f"should be identical to siret given in siren_or_siret "
                f"arg ({siren_or_siret})"
            )

    res = {}
    for identifier, vals in identifier2vals.items():
        routing_code = routing_code_name = suffix = False
        commitment_required = False
        dir_siren = vals.get("siren")
        if not dir_siren:
            raise RuntimeError("A siren key should be present")
        if siren != dir_siren:
            raise RuntimeError(
                "SIREN in directory line value must be the same as "
                "SIREN given as argument"
            )
        dir_siret = vals.get("siret")
        if dir_siret:
            if len(dir_siret) != 14:
                raise RuntimeError(
                    "SIRET in directory line {identifier} should have 14 caracters"
                )
            if not siret_is_valid(dir_siret):
                raise RuntimeError(
                    f"SIRET {dir_siret} in directory line {identifier} is invalid"
                )
            if siret and siret != dir_siret:
                raise RuntimeError(
                    "SIRET in directory line value must be the same as "
                    "SIRET given as argument"
                )
        state_map = {
            "Upcoming": "upcoming",
            "Enabled": "active",
            "Disabled": "disabled",
        }
        dir_state = vals.get("directoryLineStatus")
        if dir_state:
            if dir_state not in state_map:
                raise RuntimeError(
                    f"Directory line {identifier} has directoryLineStatus "
                    f"'{dir_state}'. This value is not expected."
                )
            state = state_map[dir_state]
        else:
            state = "disabled"

        if "routingCode" in vals:
            type = "routing_code"
            routing_dict = vals["routingCode"]
            if not isinstance(routing_dict, dict):
                raise RuntimeError(
                    f"routingCode must be a dict in directory line {identifier}"
                )
            if not dir_siret:
                raise RuntimeError(
                    f"SIRET is not provided in routing directory line {identifier}"
                )
            if "addressingSuffix" in vals:
                raise RuntimeError(
                    "Key 'addressingSuffix' should not be present in routing "
                    f"directory line {identifier}"
                )
            routing_code = routing_dict.get("routingIdentifier")
            if not routing_code:
                raise RuntimeError(
                    f"Missing 'routingIdentifier' in directory line {identifier}"
                )
            if not isinstance(routing_code, str):
                raise RuntimeError(
                    f"routingIdentifier must be a string in directory line {identifier}"
                )
            if filter_out_factures_publiques and routing_code == "FACTURES_PUBLIQUES":
                continue
            routing_code_name = routing_dict.get("routingCodeName")
            if not routing_code_name:
                raise RuntimeError(
                    f"Missing 'routingCodeName' in directory line {identifier}"
                )
            if not isinstance(routing_code_name, str):
                raise RuntimeError(
                    f"routingCodeName must be a string in directory line "
                    f"{identifier}"
                )
            routing_id_type = routing_dict.get("routingIdentifierType")
            if routing_id_type != "0224":
                raise RuntimeError(
                    f"routingIdentifierType has value {routing_id_type} "
                    f"in directory line {identifier} (expected value is '0224')"
                )
            commitment_required = routing_dict.get("managesLegalCommitmentCode", False)
            if not isinstance(commitment_required, bool):
                raise RuntimeError(
                    f"managesLegalCommitmentCode must be a boolean in "
                    f"directory line {identifier}"
                )
            if siret_parsed.get("b2g_commitment_required") and not commitment_required:
                logger.warning(
                    f"This public entity has global property commitment_required, "
                    f"but the directory line {identifier} is not marked as "
                    "commitment_required"
                )
                commitment_required = True
            expected_identifier = f"{siren}_{siret}_{routing_code}"

        elif "addressingSuffix" in vals:
            type = "suffix"
            suffix = vals["addressingSuffix"]
            if not isinstance(suffix, str):
                raise RuntimeError("Value of 'addressingSuffix' must be a string")
            if dir_siret:
                raise RuntimeError(
                    "SIRET should not be present on a directory line type suffix"
                )
            expected_identifier = f"{siren}_{suffix}"
        elif dir_siret:
            type = "siret"
            if siret_parsed.get("b2g_commitment_required"):
                logger.info(
                    f"SIRET directory line {identifier} forced to "
                    "commitment_required because the public entity has "
                    "b2g_commitment_required"
                )
                commitment_required = True
            elif siret_parsed.get("b2g_service_or_commitment_required"):
                logger.info(
                    f"SIRET directory line {identifier} forced to "
                    "commitment_required because the public entity has "
                    "b2g_service_or_commitment_required"
                )
                commitment_required = True
            if siret_parsed.get("b2g_service_required"):
                logger.info(
                    f"SIRET directory line {identifier} forced to disabled "
                    "because the public entity has service required"
                )
                state = "disabled"
            expected_identifier = f"{siren}_{siret}"
        else:
            type = "siren"
            expected_identifier = siren
        if expected_identifier != identifier:
            raise RuntimeError(
                f"Directory line {identifier} type {type} was expected to be "
                f"{expected_identifier}"
            )

        new_vals = {
            "type": type,
            "siren": siren,
            "siret": dir_siret,
            "suffix": suffix,
            "routing_code": routing_code,
            "routing_code_name": routing_code_name,
            "commitment_required": commitment_required,
            "state": state,
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
        raise ValueError(
            f"filename length is {len(filename)}, which is over the maxium (255)"
        )
    if flow_syntax not in ("CII", "UBL", "Factur-X", "CDAR", "FRR"):
        raise ValueError("flow_syntax argument has a wrong value")
    if processing_rule not in (
        "B2B",
        "B2BInt",
        "B2C",
        "B2G",
        "B2GInt",
        "OutOfScope",
        "B2GOutOfScope",
        "ArchiveOnly",
        "NotApplicable",
    ):
        raise ValueError("processing_rule argument has a wrong value")
    platform = _get_plateform(session)
    if platform not in PLATFORMS:
        raise ValueError(f"Plateform {platform} is not supported yet.")
    payload = {
        "file": (filename, BytesIO(file_bin)),
        "flowInfo": (
            None,
            json.dumps(
                {
                    "flowSyntax": flow_syntax,
                    "name": filename,
                    # not yet supported by superPDP
                    # 'processingRule': processing_rule,
                }
            ),
            "text/plain",
        ),
    }
    base_url = PLATFORMS[platform]["afnor_base_url"]
    url = f"{base_url}/afnor-flow/{AFNOR_API_VERSION}/flows"
    logger.info(f"Sending POST request on {url} (v{VERSION})")
    try:
        post_res = session.post(url, files=payload, timeout=TIMEOUT)
    except Exception as e:
        raise ConnectionError(f"POST request on {url} failed. Error: {str(e)}") from e
    status_code = post_res.status_code
    if status_code != 202:
        error_code = error_msg = None
        try:
            error_json = post_res.json()
            error_code = error_json.get("errorCode")
            error_msg = error_json.get("errorMessage")
        except Exception:
            pass
        raise RuntimeError(
            f"POST request on {url} failed ({status_code}). "
            f"Error code: {error_code}. Error message: {error_msg}"
        )
    flow_dict = post_res.json()
    logger.debug(f"Answer JSON: {flow_dict}")
    # We could check that the value received == value sent for processingRule and name
    answer_flow_syntax = flow_dict.get("flowSyntax")
    if answer_flow_syntax and answer_flow_syntax != flow_syntax:
        raise RuntimeError(
            f"Query had flowSyntax={flow_syntax} but answer has "
            f"flowSyntax={answer_flow_syntax}"
        )
    return flow_dict


def send_flow_parsed(session, file_bin, filename, flow_syntax, processing_rule):
    flow_dict = send_flow(session, file_bin, filename, flow_syntax, processing_rule)
    _parse_flow_dict(flow_dict)
    return flow_dict


def search_flows(
    session, updated_after, flow_direction, flow_type, updated_before=None
):
    # Pagination works with the updatedAfter property
    # The comparison with current date is strict : updatedAt > updatedAfter
    if not session:
        raise ValueError("session argument has no value")
    if not updated_after:
        raise ValueError("updated_after argument must have a value")
    if not isinstance(updated_after, str):
        raise ValueError("updated_after argument must be a timestamp as string")
    if not updated_after.endswith("Z"):
        raise ValueError(
            "updated_after argument must be a timestamp as string in UTC, "
            "so it should end with 'Z'"
        )

    if flow_direction:
        if isinstance(flow_direction, str):
            flow_direction = [flow_direction]
        flow_direction_values = ["In", "Out"]
        if isinstance(flow_direction, list):
            for flow_dir_value in flow_direction:
                if flow_dir_value not in flow_direction_values:
                    raise ValueError(
                        f"Value {flow_dir_value} is not allowed for the "
                        f"argument flow_direction. Allowed values: "
                        f"{flow_direction_values}"
                    )
        else:
            raise ValueError(
                "Argument flow_direction must be a list of stings (or a string)"
            )
    if flow_type:
        if isinstance(flow_type, str):
            flow_type = [flow_type]
        flow_type_values = [
            "CustomerInvoice",
            "SupplierInvoice",
            "StateInvoice",
            "CustomerInvoiceLC",
            "SupplierInvoiceLC",
            "StateCustomerInvoiceLC",
            "StateSupplierInvoiceLC",
        ]  # LC = Life Cycle
        if isinstance(flow_type, list):
            for flow_type_value in flow_type:
                if flow_type_value not in flow_type_values:
                    raise ValueError(
                        f"Value {flow_type_value} is not allowed for the "
                        f"argument flow_type. Allowed values: "
                        f"{flow_type_values}"
                    )
        else:
            raise ValueError(
                "Argument flow_type must be a list of strings (or a string)"
            )
    platform = _get_plateform(session)
    if platform not in PLATFORMS:
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
    base_url = PLATFORMS[platform]["afnor_base_url"]
    url = f"{base_url}/afnor-flow/{AFNOR_API_VERSION}/flows/search"
    next_page = True
    res = []
    while next_page:
        res_single_call = _post_search_flows(session, url, query_json)
        res += res_single_call
        if len(res_single_call) < LIMIT:
            next_page = False
        else:
            updated_after_list = [
                flow["updatedAt"] for flow in res_single_call if flow.get("updatedAt")
            ]
            if not updated_after_list:
                raise RuntimeError(
                    f"Key 'updatedAt' is not present in the key 'results' of "
                    f"the answer of {url}. This should not happen."
                )
            next_updated_after = max(updated_after_list)
            query_json["where"]["updatedAfter"] = next_updated_after
    return res


def _post_search_flows(session, url, query_json):
    logger.info(f"Sending POST request on {url} with query={query_json} (v{VERSION})")
    try:
        post_res = session.post(url, json=query_json, timeout=TIMEOUT)
    except Exception as e:
        raise ConnectionError(f"POST request on {url} failed. Error: {str(e)}") from e
    status_code = post_res.status_code
    if status_code != 200:
        error_code = error_msg = None
        try:
            error_json = post_res.json()
            error_code = error_json.get("errorCode")
            error_msg = error_json.get("errorMessage")
        except Exception:
            pass
        raise RuntimeError(
            f"POST request on {url} failed ({status_code}). "
            f"Error code: {error_code}. Error message: {error_msg}"
        )
    flows_dict = post_res.json()
    logger.debug(f"Answer JSON: {flows_dict}")
    res = flows_dict.get("results", [])
    return res


def search_flows_parsed(
    session, updated_after, flow_direction, flow_type, updated_before=None
):
    if isinstance(flow_direction, str):
        flow_direction = flow_direction.capitalize()
    elif isinstance(flow_direction, list):
        flow_direction = [x.capitalize() for x in flow_direction]
    if isinstance(updated_after, datetime.datetime):
        if updated_after.tzinfo:  # tz aware
            updated_after_utc_aware = updated_after.astimezone(pytz.utc)
        else:  # tz naive, we suppose it is UTC
            updated_after_utc_aware = pytz.utc.localize(updated_after)
        updated_after = updated_after_utc_aware.isoformat(timespec="milliseconds")
        if updated_after.endswith("+00:00"):
            updated_after = f"{updated_after[:-6]}Z"
        logger.debug(f"updated_after converted to string: {updated_after}")
    res = search_flows(
        session, updated_after, flow_direction, flow_type, updated_before=updated_before
    )
    for flow_dict in res:
        _parse_flow_dict(flow_dict)
    return res


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
        doc_type_values = ("Metadata", "Original", "Converted", "ReadableView")
        if doc_type not in doc_type_values:
            raise ValueError(
                f"Value {doc_type} is not allowed for the argument doc_type. "
                f"Allowed values: {doc_type_values}"
            )
    platform = _get_plateform(session)
    if platform not in PLATFORMS:
        raise ValueError(f"Plateform {platform} is not supported yet.")
    base_url = PLATFORMS[platform]["afnor_base_url"]
    url = f"{base_url}/afnor-flow/{AFNOR_API_VERSION}/flows/{flow_id}"
    params = {}
    if doc_type:
        params["docType"] = doc_type
    logger.info(f"Sending GET request on {url} with params {params} (v{VERSION})")
    try:
        get_res = session.get(url, params=params, timeout=TIMEOUT)
    except Exception as e:
        raise ConnectionError(f"GET request on {url} failed. Error: {str(e)}") from e
    status_code = get_res.status_code
    if status_code != 200:
        error_code = error_msg = None
        try:
            error_json = get_res.json()
            error_code = error_json.get("errorCode")
            error_msg = error_json.get("errorMessage")
        except Exception:
            pass
        raise RuntimeError(
            f"GET request on {url} failed ({status_code}). "
            f"Error code: {error_code}. Error message: {error_msg}"
        )
    if not doc_type or doc_type == "Metadata":  # Metadata is the default
        metadata_dict = get_res.json()
        logger.debug(f"Answer JSON: {metadata_dict}")
        return metadata_dict
    file_bin = get_res.content
    if not file_bin:
        raise RuntimeError(f"Empty file retrieved from {url}")
    if not isinstance(file_bin, bytes):
        raise RuntimeError(f"File retrieved from {url} is not a python bytes object")
    return file_bin


def get_flow_metadata_parsed(session, flow_id):
    if not session:
        raise ValueError("session argument has no value")
    if not flow_id:
        raise ValueError("flow_id argument has no value")
    if not isinstance(flow_id, str):
        raise ValueError("flow_id argument must be a string")
    flow_dict = get_flow(session, flow_id, doc_type="Metadata")
    _parse_flow_dict(flow_dict)
    return flow_dict


def generate_cdar(
    data_dict, check_xsd=True, check_schematron=True, prefixed_namespaces=True
):
    """Generate CDAR XML file for life cycle"""
    if prefixed_namespaces:
        RSM = objectify.ElementMaker(
            namespace=CDAR_NS_MAP["rsm"], nsmap=CDAR_NS_MAP, annotate=False
        )
        RAM = objectify.ElementMaker(namespace=CDAR_NS_MAP["ram"], annotate=False)
        UDT = objectify.ElementMaker(namespace=CDAR_NS_MAP["udt"], annotate=False)
        QDT = objectify.ElementMaker(namespace=CDAR_NS_MAP["qdt"], annotate=False)
    else:
        RSM = objectify.ElementMaker(
            namespace=CDAR_NS_MAP["rsm"],
            nsmap={None: CDAR_NS_MAP["rsm"]},
            annotate=False,
        )
        RAM = objectify.ElementMaker(
            namespace=CDAR_NS_MAP["ram"],
            nsmap={None: CDAR_NS_MAP["ram"]},
            annotate=False,
        )
        UDT = objectify.ElementMaker(
            namespace=CDAR_NS_MAP["udt"],
            nsmap={None: CDAR_NS_MAP["udt"]},
            annotate=False,
        )
        QDT = objectify.ElementMaker(
            namespace=CDAR_NS_MAP["qdt"],
            nsmap={None: CDAR_NS_MAP["qdt"]},
            annotate=False,
        )

    root = RSM.CrossDomainAcknowledgementAndResponse(
        RSM.ExchangedDocumentContext(
            RAM.BusinessProcessSpecifiedDocumentContextParameter(
                *[RAM.ID(data_dict["MDT-2"]) for _ in [1] if "MDT-2" in data_dict]
            ),
            RAM.GuidelineSpecifiedDocumentContextParameter(RAM.ID(data_dict["MDT-3"])),
        ),
        RSM.ExchangedDocument(
            RAM.ID(data_dict["MDT-4"]),
            *[RAM.Name(data_dict["MDT-5"]) for _ in [1] if "MDT-5" in data_dict],
            RAM.IssueDateTime(UDT.DateTimeString(data_dict["MDT-8"], format="204")),
            RAM.SenderTradeParty(RAM.RoleCode(data_dict["MDT-21"])),
            RAM.IssuerTradeParty(
                *[
                    RAM.GlobalID(global_id, schemeID=schemeID)
                    for (schemeID, global_id) in data_dict["MDT-38"].items()
                ],
                RAM.Name(data_dict["MDT-39"]),
                RAM.RoleCode(data_dict["MDT-40"]),
            ),
            RAM.RecipientTradeParty(
                *[
                    RAM.GlobalID(global_id, schemeID=schemeID)
                    for (schemeID, global_id) in data_dict["MDT-57"].items()
                ],
                RAM.Name(data_dict["MDT-58"]),
                RAM.RoleCode(data_dict["MDT-59"]),
                RAM.URIUniversalCommunication(
                    RAM.URIID(data_dict["MDT-73"], schemeID=data_dict["MDT-73-1"])
                ),
            ),
        ),
        RSM.AcknowledgementDocument(
            RAM.MultipleReferencesIndicator(
                UDT.Indicator(str(data_dict["MDT-74"]).lower())
            ),
            RAM.TypeCode(str(data_dict["MDT-77"])),
            RAM.IssueDateTime(UDT.DateTimeString(data_dict["MDT-78"], format="204")),
            RAM.ReferenceReferencedDocument(
                RAM.IssuerAssignedID(data_dict["MDT-87"]),
                *[
                    RAM.StatusCode(data_dict["MDT-88"])
                    for _ in [1]
                    if "MDT-88" in data_dict
                ],
                RAM.TypeCode(data_dict["MDT-91"]),
                *[
                    RAM.ReceiptDateTime(
                        UDT.DateTimeString(data_dict["MDT-95"], format="204")
                    )
                    for _ in [1]
                    if "MDT-95" in data_dict
                ],
                *[
                    RAM.AttachmentBinaryObject(
                        base64.encodebytes(attach["bin"]),
                        filename=attach["filename"],
                        mimeCode=attach["mime_type"],
                    )
                    for attach in data_dict.get("MDT-96", [])
                ],
                RAM.FormattedIssueDateTime(
                    QDT.DateTimeString(data_dict["MDT-100"], format="102")
                ),
                RAM.ProcessConditionCode(data_dict["MDT-105"]),
                RAM.ProcessCondition(data_dict["MDT-106"]),
                RAM.IssuerTradeParty(
                    *[
                        RAM.GlobalID(global_id, schemeID=schemeID)
                        for (schemeID, global_id) in data_dict["MDT-129"].items()
                    ]
                ),
                *[
                    RAM.SpecifiedDocumentStatus(
                        *[
                            RAM.ReasonCode(doc_status["MDT-113"])
                            for _ in [1]
                            if "MDT-113" in doc_status
                        ],
                        *[
                            RAM.Reason(doc_status["MDT-114"])
                            for _ in [1]
                            if "MDT-114" in doc_status
                        ],
                        *[
                            RAM.RequestedActionCode(doc_status["MDT-121"])
                            for _ in [1]
                            if "MDT-121" in doc_status
                        ],
                        *[
                            RAM.RequestedAction(doc_status["MDT-122"])
                            for _ in [1]
                            if "MDT-122" in doc_status
                        ],
                        *[
                            RAM.IncludedNote(RAM.Content(doc_status["MDT-126"]))
                            for _ in [1]
                            if "MDT-126" in doc_status
                        ],
                        *[
                            RAM.SpecifiedDocumentCharacteristic(
                                *[
                                    RAM.TypeCode(doc_characteristic["MDT-207"])
                                    for _ in [1]
                                    if "MDT-207" in doc_characteristic
                                ],
                                *[
                                    RAM.ValueChangedIndicator(
                                        UDT.IndicatorString(
                                            str(doc_characteristic["MDT-209"]).lower()
                                        )
                                    )
                                    for _ in [1]
                                    if "MDT-209" in doc_characteristic
                                ],
                                *[
                                    RAM.ValueAmount(
                                        doc_characteristic["MDT-215"]["float"],
                                        currencyID=doc_characteristic["MDT-215"][
                                            "currency"
                                        ],
                                    )
                                    for _ in [1]
                                    if "MDT-215" in doc_characteristic
                                ],
                                *[
                                    RAM.ValueDateTime(
                                        UDT.DateTimeString(
                                            doc_characteristic["MDT-219"], format="102"
                                        )
                                    )
                                    for _ in [1]
                                    if "MDT-219" in doc_characteristic
                                ],
                            )
                            for doc_characteristic in doc_status.get("MDG-43", [])
                        ],
                    )
                    for doc_status in data_dict.get("MDG-37", [])
                ],
            ),
        ),
    )

    xml_bytes = etree.tostring(
        root, pretty_print=True, xml_declaration=True, encoding="UTF-8"
    )
    if check_xsd:
        _cdar_check_xsd(xml_bytes)
    if check_schematron:
        _cdar_check_schematron(xml_bytes)
    return xml_bytes


def _cdar_check_xsd(xml_bytes):
    xsd_absolute_filepath = importlib.resources.files(__package__).joinpath(
        CDAR_XSD_FILE
    )
    logger.debug(f"Using CDAR XSD file {xsd_absolute_filepath}")
    official_schema = etree.XMLSchema(file=xsd_absolute_filepath)
    try:
        t = etree.parse(BytesIO(xml_bytes))
        official_schema.assertValid(t)
    except Exception as e:
        # if the validation of the XSD fails, we arrive here
        logger.error("The CDAR XML file is invalid against the XML Schema Definition")
        logger.error(f"XSD Error: {str(e)}")
        raise Exception(
            "The CDAR XML file is not valid against the official "
            "XML Schema Definition. "
            "Here is the error, which may give you an idea on the "
            f"cause of the problem: {str(e)}."
        ) from e
    logger.info("CDAR XML file successfully checked against XSD")


def _cdar_check_schematron(xml_bytes):
    # TODO add option to pass saxon_proc_and_style
    start_chrono = datetime.datetime.now()
    errors = []
    xml_str = xml_bytes.decode("utf-8")
    xml_str_no_bom = xml_str.lstrip("\ufeff")
    xsl_file_path = importlib.resources.files(__package__).joinpath(CDAR_XSL_FILE)
    xsl_file_path_str = str(xsl_file_path)
    with saxonche.PySaxonProcessor() as saxproc:
        xslt_proc = saxproc.new_xslt30_processor()
        xdm_node = saxproc.parse_xml(xml_text=xml_str_no_bom)
        # compile_stylesheet() is the slow/heavy part
        # So, if you pass the compiled stylesheet as argument, it saves a lot of time
        # (about 300 ms on an intel laptop)
        saxon_compiled_stylesheet = xslt_proc.compile_stylesheet(
            stylesheet_file=xsl_file_path_str
        )
        result_str = saxon_compiled_stylesheet.transform_to_string(xdm_node=xdm_node)

    try:
        svrl_root = etree.fromstring(result_str.encode("utf-8"))
    except Exception as e:
        logger.error(
            f"Schematron check generated an invalid XML output. Error: {str(e)}"
        )
        logger.info("Unable to validate CDAR XML file against schematron")
        return False
    xpath_errors = svrl_root.xpath(
        ".//svrl:successful-report | .//svrl:failed-assert", namespaces=svrl_root.nsmap
    )
    error_nr = 1
    for xpath_error in xpath_errors:
        detail_xpath = xpath_error.xpath(
            "*[local-name() = 'text']", namespaces=svrl_root.nsmap
        )
        if detail_xpath:
            error_msg = detail_xpath[0].text and detail_xpath[0].text.strip()
            error_msg = f"{error_nr}. {error_msg}"
            location = xpath_error.attrib and xpath_error.attrib.get("location")
            if location:
                error_msg = f"{error_msg}\nError location: {location}"
            errors.append(error_msg)
            error_nr += 1

    if errors:
        logger.error(
            "The XML file is invalid against the schematron: %d errors found.",
            len(errors),
        )
        for error_msg in errors:
            logger.error(error_msg)
        error_list_str = "\n".join(errors)
        full_error = (
            f"The Factur-X XML file is not valid against the official "
            f"schematron. {len(errors)} errors found:\n{error_list_str}"
        )
        raise Exception(full_error)
    end_chrono = datetime.datetime.now()
    logger.info(
        "CDAR XML file successfully validated against schematron in %s sec",
        (end_chrono - start_chrono).total_seconds(),
    )


def parse_cdar_raw(xml_bytes, check_xsd=True, check_schematron=True):
    if not xml_bytes:
        raise ValueError("xml_bytes argument has no value")
    if isinstance(xml_bytes, str):
        xml_bytes = xml_bytes.encode("utf-8")
    if not isinstance(xml_bytes, bytes):
        raise ValueError(
            f"xml_bytes argument is a {type(xml_bytes)}, it must be a bytes"
        )
    try:
        xml_root = etree.fromstring(xml_bytes)
    except Exception as e:
        raise RuntimeError(f"CDAR file is not a valid XML file. Error: {str(e)}") from e
    if check_xsd:
        _cdar_check_xsd(xml_bytes)
    if check_schematron:
        _cdar_check_schematron(xml_bytes)
    exch_doc_xp = "//rsm:CrossDomainAcknowledgementAndResponse/rsm:ExchangedDocument"
    ack_doc_xp = (
        "//rsm:CrossDomainAcknowledgementAndResponse/rsm:AcknowledgementDocument"
    )
    ref_doc_xp = f"{ack_doc_xp}/ram:ReferenceReferencedDocument"
    doc_status_xp = f"{ref_doc_xp}/ram:SpecifiedDocumentStatus"
    doc_characteristics_rel_xp = "ram:SpecifiedDocumentCharacteristic"
    attach_xp = f"{ref_doc_xp}/ram:AttachmentBinaryObject"
    xpath_dict = {
        "MDT-87": f"{ref_doc_xp}/ram:IssuerAssignedID",
        "MDT-129": f"{ref_doc_xp}/ram:IssuerTradeParty/ram:GlobalID",
        "MDT-105": f"{ref_doc_xp}/ram:ProcessConditionCode",
        "MDT-106": f"{ref_doc_xp}/ram:ProcessCondition",
        "MDT-8": f"{exch_doc_xp}/ram:IssueDateTime/udt:DateTimeString",
    }
    doc_status_xpath_dict = {
        "MDT-113": "ram:ReasonCode",
        "MDT-114": "ram:Reason",
        "MDT-121": "ram:RequestedActionCode",
        "MDT-122": "ram:RequestedAction",
        "MDT-126": "ram:IncludedNote/ram:Content",
    }
    doc_characteristics_xpath_dict = {
        "MDT-207": "ram:TypeCode",
        "MDT-209": "ram:ValueChangedIndicator/udt:IndicatorString",
        "MDT-215": "ram:ValueAmount",
        "MDT-219": "ram:ValueDateTime/udt:DateTimeString",
    }

    res = {"MDG-37": [], "MDT-96": []}
    namespaces = xml_root.nsmap
    if None in namespaces:
        namespaces.pop(None)
    namespaces = CDAR_NS_MAP
    for key, xpath in xpath_dict.items():
        value = _xpath_get_value(xpath, xml_root, namespaces)
        if value is not None:
            res[key] = value
    doc_status_line = 0
    for doc_status in xml_root.xpath(doc_status_xp, namespaces=namespaces):
        doc_status_line += 1
        doc_status_dict = {"MDG-43": []}
        for key, xpath in doc_status_xpath_dict.items():
            value = _xpath_get_value(xpath, doc_status, namespaces)
            if value is not None:
                doc_status_dict[key] = value
        for doc_characteristic in doc_status.xpath(
            doc_characteristics_rel_xp, namespaces=namespaces
        ):
            doc_characteristic_dict = {}
            for key, xpath in doc_characteristics_xpath_dict.items():
                value = _xpath_get_value(xpath, doc_characteristic, namespaces)
                if value is not None:
                    doc_characteristic_dict[key] = value
            doc_status_dict["MDG-43"].append(doc_characteristic_dict)
        res["MDG-37"].append(doc_status_dict)
    for attach in xml_root.xpath(attach_xp, namespaces=namespaces):
        if attach.text:
            if attach.attrib and attach.attrib.get("filename"):
                filename = attach.attrib["filename"]
            else:
                filename = "unknwon_filename.bin"
            avals = {
                "bin": base64.b64decode(attach.text),
                "filename": filename,
            }
            if attach.attrib and attach.attrib.get("mimeCode"):
                avals["mime_type"] = attach.attrib["mimeCode"]
            res["MDT-96"].append(avals)
    return res


def _xpath_get_value(xpath, node, namespaces):
    date_fmt = {
        "102": "%Y%m%d",
        "204": "%Y%m%d%H%M%S",
    }
    xpath_res = node.xpath(xpath, namespaces=namespaces)
    values = []
    for xpath_entry in xpath_res:
        if xpath_entry.text:
            value = xpath_entry.text and xpath_entry.text.strip()
            if (
                value
                and xpath.endswith(":DateTimeString")
                and xpath_entry.attrib
                and xpath_entry.attrib.get("format") in date_fmt
            ):
                value = datetime.datetime.strptime(
                    value, date_fmt[xpath_entry.attrib["format"]]
                )
            elif value and xpath_entry.attrib and xpath_entry.attrib.get("currencyID"):
                value = {
                    "float": float(value),
                    "currency": xpath_res[0].attrib["currencyID"],
                }
            elif value and xpath_entry.attrib and xpath_entry.attrib.get("schemeID"):
                value = {
                    "schemeID": xpath_entry.attrib["schemeID"],
                    "text": value,
                }
            if value:
                values.append(value)
    if not values:
        values = None
    elif isinstance(values[0], dict) and "schemeID" in values[0]:
        values = {x["schemeID"]: x["text"] for x in values}
    elif len(values) == 1:
        values = values[0]
    return values


def _map_nested_keys(data, key_map):
    """Recursively updates keys in a dictionary based on a mapping dictionary"""
    if isinstance(data, dict):
        return {
            key_map.get(k, k): _map_nested_keys(v, key_map) for k, v in data.items()
        }
    elif isinstance(data, list):
        return [_map_nested_keys(item, key_map) for item in data]
    else:
        return data


def parse_cdar(xml_bytes, check_xsd=True, check_schematron=True):
    raw_res = parse_cdar_raw(
        xml_bytes, check_xsd=check_xsd, check_schematron=check_schematron
    )
    key_map = {
        "MDT-87": "invoice_number",
        "MDT-129": "invoice_issuer",
        "MDT-96": "attachments",
        "MDT-105": "status_code",
        "MDT-106": "status_name",
        "MDT-8": "lc_datetime",
        "MDT-113": "reason_code",
        "MDT-114": "reason_txt",
        "MDT-121": "action_code",
        "MDT-122": "action_txt",
        "MDT-126": "comment",
        "MDT-207": "type_code",
        "MDT-215": "amount",
        "MDT-219": "date",
        "MDG-37": "doc_status",
        "MDG-43": "doc_characteristics",
    }
    res = _map_nested_keys(raw_res, key_map)
    return res


def _parse_flow_dict(flow_dict):
    state_map = {  # key = AFNOR vals ; values = our keys
        "Pending": "sent",
        "Ok": "done",
        "Error": "error",
    }
    direction_map = {
        "In": "in",
        "Out": "out",
    }
    if flow_dict.get("submittedAt"):
        flow_dict["submitted_at"] = _timestamp_iso8601_to_utc_datetime(
            flow_dict["submittedAt"]
        )
    if flow_dict.get("updatedAt"):
        flow_dict["updated_at"] = _timestamp_iso8601_to_utc_datetime(
            flow_dict["updatedAt"]
        )
    if flow_dict.get("acknowledgement"):
        if flow_dict["acknowledgement"].get("status"):
            flow_dict["state"] = state_map.get(
                flow_dict["acknowledgement"]["status"], "ap_unknown"
            )
        if flow_dict["acknowledgement"].get("details") and isinstance(
            flow_dict["acknowledgement"]["details"], list
        ):
            messages = []
            for detail in flow_dict["acknowledgement"]["details"]:
                # the 4 fields are required, so the IF condition should always be ok
                if (
                    detail.get("item")
                    and detail.get("level")
                    and detail.get("reasonCode")
                    and detail.get("reasonMessage")
                ):
                    msg = (
                        f"{detail['level']} on {detail['item']}: "
                        f"{detail['reasonMessage']} (code: {detail['reasonCode']})"
                    )
                    messages.append(msg)
            flow_dict["ap_error_details"] = "\n".join(messages) or False
    if flow_dict.get("flowDirection"):
        flow_dict["flow_direction"] = direction_map.get(
            flow_dict["flowDirection"], flow_dict["flowDirection"]
        )


def _timestamp_iso8601_to_utc_datetime(timestamp):
    if not timestamp:
        raise ValueError("timestamp argument has no value")
    if not isinstance(timestamp, str):
        raise ValueError("timestamp argument must be a string")
    timestamp_dt = datetime.datetime.fromisoformat(timestamp)
    # switch to UTC
    timestamp_dt_utc = timestamp_dt.astimezone(pytz.utc)
    timestamp_dt_utc_naive = timestamp_dt_utc.replace(tzinfo=None)
    return timestamp_dt_utc_naive
