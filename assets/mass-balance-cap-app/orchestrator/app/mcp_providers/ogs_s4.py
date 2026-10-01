"""
CF-native OGS_S4 destination client.
Reads VCAP_SERVICES to get the BTP Destination Service credentials,
then calls SAP S/4HANA IS-Oil & Gas OData APIs via OGS_S4 destination.
No sap_cloud_sdk required — pure CF + BTP Destination Service REST API.
"""
import json
import logging
import os
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# ── BTP Destination Service (VCAP_SERVICES) ────────────────────────────────

def _get_destination_service_credentials() -> dict:
    """Read BTP Destination Service credentials from VCAP_SERVICES."""
    vcap = os.environ.get("VCAP_SERVICES", "{}")
    services = json.loads(vcap)
    # BTP Destination Service binding name is 'destination'
    for key in ("destination", "Destination"):
        for svc in services.get(key, []):
            creds = svc.get("credentials", {})
            if creds.get("uri") and creds.get("clientid"):
                return creds
    raise RuntimeError("BTP Destination Service not bound. Bind 'destination' service to the CF app.")


def _get_xsuaa_token(creds: dict) -> str:
    """Get OAuth2 token from XSUAA using client credentials."""
    url = f"{creds['url']}/oauth/token"
    resp = httpx.post(
        url,
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


def _get_destination_url(creds: dict, token: str, destination_name: str) -> tuple[str, dict]:
    """
    Fetch destination URL and auth headers from BTP Destination Service.
    Returns (base_url, auth_headers).
    """
    dest_uri = creds["uri"]
    resp = httpx.get(
        f"{dest_uri}/destination-configuration/v1/destinations/{destination_name}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    dest_config = data.get("destinationConfiguration", {})
    base_url = dest_config.get("URL", "")

    # Auth headers injected by BTP Destination Service
    auth_token_data = data.get("authTokens", [])
    auth_headers = {}
    if auth_token_data:
        first = auth_token_data[0]
        auth_headers["Authorization"] = f"{first.get('type', 'Bearer')} {first.get('value', '')}"

    return base_url, auth_headers


# ── OGS_S4 OData Client ────────────────────────────────────────────────────

class OGSS4Client:
    """
    CF-native client for SAP IS-Oil & Gas OData APIs via OGS_S4 BTP destination.
    Uses BTP Destination Service to resolve URL and inject auth headers.
    """

    DESTINATION_NAME = "OGS_S4"

    def __init__(self):
        self._base_url: Optional[str] = None
        self._auth_headers: dict = {}
        self._http: Optional[httpx.AsyncClient] = None

    async def _ensure_connected(self):
        """Lazy connect — resolve destination on first use."""
        if self._base_url:
            return
        try:
            creds = _get_destination_service_credentials()
            token = _get_xsuaa_token(creds)
            self._base_url, self._auth_headers = _get_destination_url(
                creds, token, self.DESTINATION_NAME
            )
            self._http = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    **self._auth_headers,
                    "Accept": "application/json",
                    "sap-client": os.environ.get("SAP_CLIENT", "100"),
                },
                timeout=60,
            )
            logger.info("Connected to OGS_S4 destination: %s", self._base_url)
        except Exception as e:
            logger.error("Failed to connect to OGS_S4 destination: %s", e)
            raise

    async def get(self, path: str, params: Optional[dict] = None) -> dict:
        """Make a GET request to the OGS_S4 OData API."""
        await self._ensure_connected()
        resp = await self._http.get(path, params={"$format": "json", **(params or {})})
        resp.raise_for_status()
        return resp.json()

    # ── Mass Balance Data Domains ──────────────────────────────────────────

    async def get_material_stock(self, plant: str, material: Optional[str] = None) -> dict:
        """TANK/MAT domain — Read material stock levels (MARD)."""
        params = {"$filter": f"Plant eq '{plant}'"}
        if material:
            params["$filter"] += f" and Material eq '{material}'"
        return await self.get("/sap/opu/odata/sap/API_MATERIAL_STOCK_SRV/A_MatlStkInAcctMod", params)

    async def get_material_documents(self, plant: str, posting_date: str) -> dict:
        """MOV domain — Read material movements (MSEG/MKPF)."""
        return await self.get(
            "/sap/opu/odata/sap/API_MATERIAL_DOCUMENT_SRV/A_MaterialDocumentHeader",
            {"$filter": f"Plant eq '{plant}' and PostingDate eq datetime'{posting_date}T00:00:00'",
             "$expand": "to_MaterialDocumentItem"}
        )

    async def get_physical_inventory_documents(self, plant: str) -> dict:
        """PHYS domain — Read physical inventory documents (MI01/MI07)."""
        return await self.get(
            "/sap/opu/odata/sap/CE_PHYSICALINVENTORYDOCUMENT_0001/PhysInventoryDocHeader",
            {"$filter": f"Plant eq '{plant}'"}
        )

    async def get_stock_transport_orders(self, supplying_plant: str) -> dict:
        """TRANSFERS domain — Read stock transport orders."""
        return await self.get(
            "/sap/opu/odata/sap/CE_STOCKTRANSPORTORDER_0001/A_StockTransportOrder",
            {"$filter": f"SupplyingPlant eq '{supplying_plant}'"}
        )

    async def get_process_order_confirmations(self, plant: str) -> dict:
        """BOOK domain — Read process order confirmations (yield/consumption)."""
        return await self.get(
            "/sap/opu/odata/sap/API_PROC_ORDER_CONFIRMATION_2_SRV/A_ProcOrdConfirmation",
            {"$filter": f"Plant eq '{plant}'"}
        )

    async def close(self):
        if self._http:
            await self._http.aclose()


# ── Singleton ──────────────────────────────────────────────────────────────
_client: Optional[OGSS4Client] = None


def get_ogs_s4_client() -> OGSS4Client:
    global _client
    if _client is None:
        _client = OGSS4Client()
    return _client
