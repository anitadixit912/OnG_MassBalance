"""
CF-native SAP AI Core client via BTP Destination Service.
Resolves the 'aicore' destination and returns LiteLLM-compatible params.
"""
import json
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)
_cache: dict = {}


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
    Uses openai/ prefix with deployment-specific URL — bypasses LiteLLM SAP provider.
    """
    global _cache
    if _cache:
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
