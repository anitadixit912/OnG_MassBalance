"""
CF-native SAP AI Core client via BTP Destination Service.
Resolves the 'aicore' destination and returns LiteLLM-compatible params.
"""
import json
import logging
import os
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)
_cache: dict = {}
_cache_expiry: float = 0


def _get_destination_credentials() -> dict:
    vcap = os.environ.get("VCAP_SERVICES", "{}")
    for key in ("destination", "Destination"):
        for svc in json.loads(vcap).get(key, []):
            creds = svc.get("credentials", {})
            if creds.get("uri") and creds.get("clientid"):
                return creds
    raise RuntimeError("BTP Destination Service not bound.")


def _get_xsuaa_token(creds: dict) -> str:
    resp = httpx.post(
        f"{creds['url']}/oauth/token",
        data={"grant_type": "client_credentials",
              "client_id": creds["clientid"],
              "client_secret": creds["clientsecret"]},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _resolve_destination(creds: dict, token: str, name: str) -> tuple[str, str]:
    resp = httpx.get(
        f"{creds['uri']}/destination-configuration/v1/destinations/{name}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    base_url = data.get("destinationConfiguration", {}).get("URL", "").rstrip("/")
    auth_tokens = data.get("authTokens", [])
    bearer = auth_tokens[0].get("value", "") if auth_tokens else ""
    return base_url, bearer


def get_aicore_litellm_params(destination_name: str = "aicore") -> dict:
    """
    Returns LiteLLM params for SAP AI Core via BTP Destination Service.
    Token is refreshed every 10 minutes to avoid 401 from stale bearer tokens.
    """
    global _cache, _cache_expiry
    if _cache and time.time() < _cache_expiry:
        return _cache

    try:
        deployment_id = os.environ.get("AICORE_DEPLOYMENT_ID", "")
        resource_group = os.environ.get("AICORE_RESOURCE_GROUP", "default")

        creds = _get_destination_credentials()
        token = _get_xsuaa_token(creds)
        base_url, bearer = _resolve_destination(creds, token, destination_name)

        # SAP AI Core OpenAI-compatible endpoint
        api_base = f"{base_url}/v2/inference/deployments/{deployment_id}"

        _cache = {
            "model": f"openai/{deployment_id}",
            "api_base": api_base,
            "api_key": bearer,
            "extra_headers": {"AI-Resource-Group": resource_group},
        }
        _cache_expiry = time.time() + 600  # refresh every 10 minutes
        logger.info("AI Core resolved: %s", api_base)
        return _cache

    except Exception as e:
        logger.warning("Could not resolve AI Core destination: %s", e)
        return {
            "model": f"openai/{os.environ.get('AICORE_DEPLOYMENT_ID', 'dbc88cbc32f1206e')}",
            "api_base": os.environ.get("AICORE_BASE_URL", ""),
            "api_key": os.environ.get("AICORE_API_KEY", "dummy"),
            "extra_headers": {"AI-Resource-Group": os.environ.get("AICORE_RESOURCE_GROUP", "default")},
        }
