"""
CF-native SAP AI Core client via BTP Destination Service.
Reads VCAP_SERVICES to resolve the 'aicore' destination,
then provides an OpenAI-compatible base_url + api_key for LiteLLM.
No sap_cloud_sdk required — pure CF + BTP Destination Service REST API.
"""
import json
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def _get_destination_service_credentials() -> dict:
    """Read BTP Destination Service credentials from VCAP_SERVICES."""
    vcap = os.environ.get("VCAP_SERVICES", "{}")
    services = json.loads(vcap)
    for key in ("destination", "Destination"):
        for svc in services.get(key, []):
            creds = svc.get("credentials", {})
            if creds.get("uri") and creds.get("clientid"):
                return creds
    raise RuntimeError(
        "BTP Destination Service not bound. "
        "Bind 'destination' service instance to the CF app."
    )


def _get_xsuaa_token(creds: dict) -> str:
    """Get OAuth2 token from XSUAA using client credentials."""
    resp = httpx.post(
        f"{creds['url']}/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": creds["clientid"],
            "client_secret": creds["clientsecret"],
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _resolve_destination(creds: dict, token: str, destination_name: str) -> tuple[str, str]:
    """
    Resolve destination URL and bearer token from BTP Destination Service.
    Returns (base_url, bearer_token).
    """
    resp = httpx.get(
        f"{creds['uri']}/destination-configuration/v1/destinations/{destination_name}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    base_url = data.get("destinationConfiguration", {}).get("URL", "")
    auth_tokens = data.get("authTokens", [])
    bearer = auth_tokens[0].get("value", "") if auth_tokens else ""
    return base_url, bearer


# ── Public API ─────────────────────────────────────────────────────────────

_cache: dict = {}


def get_aicore_litellm_params(destination_name: str = "aicore") -> dict:
    """
    Returns LiteLLM-compatible params for SAP AI Core via BTP destination.

    Usage in LiteLLM / ChatLiteLLM:
        params = get_aicore_litellm_params()
        llm = ChatLiteLLM(
            model=params["model"],
            api_base=params["api_base"],
            api_key=params["api_key"],
        )
    """
    global _cache
    if _cache:
        return _cache

    try:
        creds = _get_destination_service_credentials()
        token = _get_xsuaa_token(creds)
        base_url, bearer = _resolve_destination(creds, token, destination_name)

        # SAP AI Core OpenAI-compatible endpoint
        api_base = base_url.rstrip("/") + "/v2"

        _cache = {
            "api_base": api_base,
            "api_key": bearer,
            # Default model — can be overridden via env var
            "model": os.environ.get(
                "AI_MODEL",
                "anthropic--claude-3.5-sonnet"
            ),
        }
        logger.info("AI Core destination resolved: %s", api_base)
        return _cache

    except Exception as e:
        logger.warning(
            "Could not resolve AI Core destination '%s': %s. "
            "Falling back to env-based config.",
            destination_name, e
        )
        # Fallback — use env vars directly (for local testing)
        return {
            "api_base": os.environ.get("AICORE_BASE_URL", ""),
            "api_key": os.environ.get("AICORE_API_KEY", "dummy"),
            "model": os.environ.get("AI_MODEL", "openai/gpt-4o"),
        }
