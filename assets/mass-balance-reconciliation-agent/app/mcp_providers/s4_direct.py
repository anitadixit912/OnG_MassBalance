"""
Direct SAP S/4HANA OData tools via BTP Destination + Connectivity Service.
Bypasses Agent Gateway — works with BasicAuthentication + OnPremise (Cloud Connector).

Flow:
  VCAP_SERVICES[destination]  → Destination Service token
  Destination Service         → OGS_S4 config + Basic auth header
  VCAP_SERVICES[connectivity] → Connectivity Service token (Proxy-Authorization)
  connectivityproxy:20003     → Cloud Connector APAC_DEV10 → http://10.236.250.15:8001
"""
import json
import logging
import os
from typing import Any

import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Ordered (service_path, entity_set) pairs to try for each domain.
# Both 403 and 404 trigger fallback to the next entry.
# Order: confirmed-403 (service exists, just needs auth) first, then 404 fallbacks.
# ZC_ prefix = actual registered URL in this OGS/650 system.
_STOCK_PATHS = [
    ("/sap/opu/odata/sap/OGS_MATERIAL_STOCK_SRV", "MaterialStockSet"),
    ("/sap/opu/odata/sap/OGS_MATERIAL_STOCK_SRV", "StockBalanceSet"),
    ("/sap/opu/odata/sap/OGS_MATERIAL_STOCK_SRV", "MaterialStock"),
    ("/sap/opu/odata/sap/OGS_MATERIAL_STOCK_SRV", "InventoryStockSet"),
    ("/sap/opu/odata/sap/ZC_STOCKQUANTITYVALUEBYTYPE_CDS", "C_StockQuantityValueByType"),
    ("/sap/opu/odata/sap/ZC_STOCKQUANTITYVALUEBYTYPE_CDS", "StockQuantityValueByType"),
    ("/sap/opu/odata/sap/API_MATERIAL_STOCK_SRV", "MatlStkInAcctMod"),
    ("/sap/opu/odata/sap/C_STOCKQUANTITYVALUEBYTYPE_CDS", "C_StockQuantityValueByType"),
]

_MOVEMENT_PATHS = [
    ("/sap/opu/odata/sap/OGS_MATERIAL_DOCUMENT_SRV", "MaterialDocumentSet"),
    ("/sap/opu/odata/sap/OGS_MATERIAL_DOCUMENT_SRV", "GoodsMovementSet"),
    ("/sap/opu/odata/sap/OGS_MATERIAL_DOCUMENT_SRV", "MatDocumentSet"),
    ("/sap/opu/odata/sap/ZMMIM_GOODS_MOVEMENT_SRV", "GoodsMovementSet"),
    ("/sap/opu/odata/sap/MMIM_GOODS_MOVEMENT_SRV", "GoodsMovementSet"),
    ("/sap/opu/odata/sap/API_MATERIAL_DOCUMENT_SRV", "MaterialDocumentItem"),
]

# CDS service for manufacturing/process order scrap (feeds BOOK domain)
_SCRAP_PATH = ("/sap/opu/odata/sap/C_MFGORDITEMMATERIALSCRAPQ_CDS", "C_MfgOrdItemMaterialScrapQ")


# --------------------------------------------------------------------------- #
# Auth / connectivity helpers                                                   #
# --------------------------------------------------------------------------- #

_cfg_cache: dict = {}


async def _load_s4_config() -> dict:
    """Load OGS_S4 destination + Connectivity Service config from VCAP_SERVICES."""
    global _cfg_cache
    if _cfg_cache:
        return _cfg_cache

    vcap_raw = os.environ.get("VCAP_SERVICES", "{}")
    try:
        services = json.loads(vcap_raw)
    except Exception:
        services = {}

    cfg: dict = {
        "s4_url": "",
        "s4_auth": "",
        "scc_location": "APAC_DEV10",
        "sap_client": "650",
        "conn_token": "",
        "proxy_url": "http://connectivityproxy.internal.cf.us10.hana.ondemand.com:20003",
    }

    # 1. Destination Service token
    dest_creds: dict | None = None
    for svc in services.get("destination", []):
        c = svc.get("credentials", {})
        if c.get("clientid") and c.get("uri"):
            dest_creds = c
            break

    if not dest_creds:
        logger.warning("No Destination Service binding found in VCAP_SERVICES")
        return cfg

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{dest_creds['url']}/oauth/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": dest_creds["clientid"],
                    "client_secret": dest_creds["clientsecret"],
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            r.raise_for_status()
            dest_token = r.json()["access_token"]
    except Exception as e:
        logger.warning("Destination Service token failed: %s", e)
        return cfg

    # 2. Resolve OGS_S4 destination
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"{dest_creds['uri']}/destination-configuration/v1/destinations/OGS_S4",
                headers={"Authorization": f"Bearer {dest_token}"},
            )
            r.raise_for_status()
            dest_data = r.json()

        d_cfg = dest_data.get("destinationConfiguration", {})
        cfg["s4_url"] = d_cfg.get("URL", "").rstrip("/")
        cfg["scc_location"] = d_cfg.get("CloudConnectorLocationId", "APAC_DEV10")
        cfg["sap_client"] = d_cfg.get("sap-client", "650")

        for tok in dest_data.get("authTokens", []):
            if tok.get("type", "").lower() in ("basic", "basicauthentication"):
                cfg["s4_auth"] = f"Basic {tok['value']}"
                break

        logger.info("OGS_S4 resolved: url=%s scc=%s", cfg["s4_url"], cfg["scc_location"])
    except Exception as e:
        logger.warning("OGS_S4 destination resolution failed: %s", e)

    # 3. Connectivity Service token (for Proxy-Authorization)
    for svc in services.get("connectivity", []):
        c = svc.get("credentials", {})
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    f"{c['token_service_url']}/oauth/token",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": c["clientid"],
                        "client_secret": c["clientsecret"],
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                r.raise_for_status()
                cfg["conn_token"] = r.json()["access_token"]
            logger.info("Connectivity Service token obtained")
        except Exception as e:
            logger.warning("Connectivity Service token failed: %s", e)
        break

    _cfg_cache = cfg
    return cfg


async def _s4_get(path: str, params: dict | None = None) -> dict:
    """GET an OData resource from S/4HANA via the CF Connectivity proxy."""
    cfg = await _load_s4_config()

    if not cfg.get("s4_url"):
        raise RuntimeError("OGS_S4 destination URL not configured")
    if not cfg.get("s4_auth"):
        raise RuntimeError("OGS_S4 auth token not available from Destination Service")

    request_headers: dict = {
        "Authorization": cfg["s4_auth"],
        "sap-client": cfg["sap_client"],
        "SAP-Connectivity-SCC-Location_ID": cfg["scc_location"],
        "Accept": "application/json",
    }

    # Include sap-client as URL param — some on-prem ICM configs strip headers
    merged_params: dict = {"sap-client": cfg["sap_client"]}
    if params:
        merged_params.update(params)

    mounts: dict | None = None
    if cfg.get("conn_token"):
        proxy = httpx.Proxy(
            url=cfg["proxy_url"],
            headers={"Proxy-Authorization": f"Bearer {cfg['conn_token']}"},
        )
        mounts = {"http://": httpx.AsyncHTTPTransport(proxy=proxy)}

    url = f"{cfg['s4_url']}{path}"
    logger.info("S4 OData GET %s", url)

    client_kwargs: dict = {"timeout": 60}
    if mounts:
        client_kwargs["mounts"] = mounts

    async with httpx.AsyncClient(**client_kwargs) as client:
        r = await client.get(url, headers=request_headers, params=merged_params)
        if not r.is_success:
            body = r.text[:500]
            raise httpx.HTTPStatusError(
                f"HTTP {r.status_code} for {url}: {body}",
                request=r.request,
                response=r,
            )
        try:
            return r.json()
        except Exception:
            return r.text  # fallback for XML (e.g. $metadata)


def _fmt_odata(data: dict) -> list[dict]:
    """Extract entity list from OData v2/v4 response."""
    if "value" in data:
        return data["value"]
    if "d" in data:
        v = data["d"]
        if "results" in v:
            return v["results"]
        if isinstance(v, list):
            return v
        return [v]
    return [data]


# --------------------------------------------------------------------------- #
# Tool 1: get_material_stock                                                    #
# --------------------------------------------------------------------------- #

class MaterialStockInput(BaseModel):
    plant: str = Field(description="SAP plant code, e.g. '1000'")
    material: str = Field(description="SAP material number, e.g. 'CRUDE01' or '000000000000000041'")
    storage_location: str = Field(default="", description="Optional storage location code")


async def _get_material_stock(plant: str, material: str, storage_location: str = "") -> str:
    """Fetch current material stock from SAP (tries multiple OData service paths)."""
    filters = [f"Plant eq '{plant}'", f"Material eq '{material}'"]
    if storage_location:
        filters.append(f"StorageLocation eq '{storage_location}'")

    tried: list[str] = []
    for svc_path, entity in _STOCK_PATHS:
        path_desc = f"{svc_path}/{entity}"
        tried.append(path_desc)
        try:
            data = await _s4_get(
                f"{svc_path}/{entity}",
                params={"$filter": " and ".join(filters), "$format": "json", "$top": "50"},
            )
            rows = _fmt_odata(data)
            if not rows:
                return json.dumps({"status": "no_data", "plant": plant, "material": material})

            result = []
            for r in rows:
                result.append({
                    "Material": r.get("Material", r.get("Matnr", "")),
                    "Plant": r.get("Plant", r.get("Werks", "")),
                    "StorageLocation": r.get("StorageLocation", r.get("Lgort", "")),
                    "Unit": r.get("MaterialBaseUnit", r.get("Meins", "")),
                    "UnrestrictedStock": r.get("MatlWrhsStkQtyInMatlBaseUnit", r.get("Labst", r.get("UnrestrictedStock", "0"))),
                    "QIStock": r.get("QualityInspectionStockQuantity", r.get("QIStock", "0")),
                    "BlockedStock": r.get("BlockedStockQuantity", r.get("BlockedStock", "0")),
                })
            return json.dumps({"status": "ok", "service": path_desc, "records": result, "count": len(result)})

        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 404):
                logger.info("Service %s returned %s — trying next path", path_desc, e.response.status_code)
                tried.append(f"{path_desc} [HTTP {e.response.status_code}]")
                continue
            return json.dumps({"status": "error", "service": path_desc, "code": e.response.status_code, "message": str(e)})
        except Exception as e:
            tried.append(f"{path_desc} [error: {type(e).__name__}]")
            return json.dumps({"status": "error", "service": path_desc, "message": str(e)})

    return json.dumps({"status": "error", "message": f"No accessible stock service found. Tried: {tried}"})


# --------------------------------------------------------------------------- #
# Tool 2: get_material_documents                                                #
# --------------------------------------------------------------------------- #

class MaterialDocumentsInput(BaseModel):
    plant: str = Field(description="SAP plant code, e.g. '1000'")
    material: str = Field(description="SAP material number")
    date_from: str = Field(description="Posting date from (YYYY-MM-DD)")
    date_to: str = Field(description="Posting date to (YYYY-MM-DD)")
    movement_type: str = Field(default="", description="Optional SAP movement type filter, e.g. '101','201','261'")


async def _get_material_documents(plant: str, material: str, date_from: str, date_to: str, movement_type: str = "") -> str:
    """Fetch goods movement material documents from SAP (tries multiple OData service paths)."""
    dt_from = f"datetime'{date_from}T00:00:00'"
    dt_to = f"datetime'{date_to}T23:59:59'"

    filters = [
        f"Plant eq '{plant}'",
        f"Material eq '{material}'",
        f"PostingDate ge {dt_from}",
        f"PostingDate le {dt_to}",
    ]
    if movement_type:
        filters.append(f"GoodsMovementType eq '{movement_type}'")

    tried: list[str] = []
    for svc_path, entity in _MOVEMENT_PATHS:
        path_desc = f"{svc_path}/{entity}"
        tried.append(path_desc)
        try:
            data = await _s4_get(
                f"{svc_path}/{entity}",
                params={
                    "$filter": " and ".join(filters),
                    "$format": "json",
                    "$top": "200",
                },
            )
            rows = _fmt_odata(data)
            result = []
            for r in rows:
                result.append({
                    "MaterialDocument": r.get("MaterialDocument", r.get("Mblnr", "")),
                    "Item": r.get("MaterialDocumentItem", r.get("Zeile", "")),
                    "PostingDate": r.get("PostingDate", r.get("Budat", "")),
                    "GoodsMovementType": r.get("GoodsMovementType", r.get("Bwart", "")),
                    "Quantity": r.get("QuantityInBaseUnit", r.get("Menge", "0")),
                    "Unit": r.get("BaseUnit", r.get("Meins", "")),
                    "Plant": r.get("Plant", r.get("Werks", "")),
                    "StorageLocation": r.get("StorageLocation", r.get("Lgort", "")),
                })
            return json.dumps({"status": "ok", "service": path_desc, "records": result, "count": len(result)})

        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 404):
                logger.info("Service %s returned %s — trying next path", path_desc, e.response.status_code)
                continue
            return json.dumps({"status": "error", "service": path_desc, "code": e.response.status_code, "message": str(e)})
        except Exception as e:
            return json.dumps({"status": "error", "service": path_desc, "message": str(e)})

    return json.dumps({"status": "error", "message": f"No accessible movement service found. Tried: {tried}"})


# --------------------------------------------------------------------------- #
# Tool 3: run_mass_balance_calculation                                          #
# --------------------------------------------------------------------------- #

class MassBalanceInput(BaseModel):
    plant: str = Field(description="SAP plant code, e.g. '1000'")
    material: str = Field(description="SAP material number")
    period_from: str = Field(description="Period start date (YYYY-MM-DD)")
    period_to: str = Field(description="Period end date (YYYY-MM-DD)")
    opening_stock: float = Field(default=0.0, description="Opening stock quantity (if known separately)")


async def _run_mass_balance(plant: str, material: str, period_from: str, period_to: str, opening_stock: float = 0.0) -> str:
    """
    Orchestrates a mass balance calculation using live S/4HANA data.
    Closing = Opening + Receipts - Issues - Consumption ± Transfers ± Adjustments
    """
    # Fetch current stock
    stock_json = await _get_material_stock(plant=plant, material=material)
    stock_data = json.loads(stock_json)

    # Fetch goods movements for period
    movements_json = await _get_material_documents(
        plant=plant, material=material,
        date_from=period_from, date_to=period_to
    )
    movements_data = json.loads(movements_json)

    if stock_data.get("status") == "error" or movements_data.get("status") == "error":
        return json.dumps({
            "status": "error",
            "stock_fetch": stock_data,
            "movements_fetch": movements_data,
        })

    # Classify movements by SAP movement type
    receipts = 0.0
    issues = 0.0
    consumption = 0.0
    transfers_in = 0.0
    transfers_out = 0.0
    adjustments = 0.0

    movement_summary: list = []
    for doc in movements_data.get("records", []):
        qty = float(doc.get("Quantity", 0) or 0)
        mvt = str(doc.get("GoodsMovementType", ""))
        category = _classify_movement(mvt)
        movement_summary.append({**doc, "Category": category})

        if category == "RECEIPT":
            receipts += qty
        elif category == "ISSUE":
            issues += qty
        elif category == "CONSUMPTION":
            consumption += qty
        elif category == "TRANSFER_IN":
            transfers_in += qty
        elif category == "TRANSFER_OUT":
            transfers_out += qty
        elif category == "ADJUSTMENT":
            adjustments += qty

    # Determine opening stock
    if opening_stock == 0.0:
        # Use current closing stock + reverse movements as approximation
        current_stock = 0.0
        for rec in stock_data.get("records", []):
            try:
                current_stock += float(rec.get("MatlWrhsStkQtyInMatlBaseUnit", 0) or 0)
            except (TypeError, ValueError):
                pass
        # Approximate opening = current + issues + consumption + transfers_out - receipts - transfers_in - adjustments
        opening_stock = current_stock + issues + consumption + transfers_out - receipts - transfers_in - adjustments

    closing_stock = opening_stock + receipts - issues - consumption + transfers_in - transfers_out + adjustments

    # Calculate variance vs system stock
    system_closing = 0.0
    for rec in stock_data.get("records", []):
        try:
            system_closing += float(rec.get("MatlWrhsStkQtyInMatlBaseUnit", 0) or 0)
        except (TypeError, ValueError):
            pass

    variance = closing_stock - system_closing
    throughput = receipts + issues + consumption
    variance_pct = (abs(variance) / throughput * 100) if throughput > 0 else 0.0

    severity = "INFO"
    if variance_pct > 2.0 or abs(variance) > 20:
        severity = "CRITICAL"
    elif variance_pct > 0.5 or abs(variance) > 5:
        severity = "WARNING"
    elif variance_pct > 0.1 or abs(variance) > 1:
        severity = "ADVISORY"

    return json.dumps({
        "status": "ok",
        "plant": plant,
        "material": material,
        "period": f"{period_from} to {period_to}",
        "mass_balance": {
            "opening_stock": round(opening_stock, 3),
            "receipts": round(receipts, 3),
            "issues": round(issues, 3),
            "consumption": round(consumption, 3),
            "transfers_in": round(transfers_in, 3),
            "transfers_out": round(transfers_out, 3),
            "adjustments": round(adjustments, 3),
            "calculated_closing": round(closing_stock, 3),
            "system_closing": round(system_closing, 3),
            "variance": round(variance, 3),
            "variance_pct": round(variance_pct, 2),
            "variance_severity": severity,
        },
        "movement_count": len(movements_data.get("records", [])),
        "movement_summary": movement_summary[:20],  # limit for context
    })


def _classify_movement(mvt_type: str) -> str:
    """Map SAP movement type code to mass balance category."""
    mvt = mvt_type.strip()
    receipts = {"101", "102", "501", "502", "531", "532", "561", "562", "901", "902"}
    issues = {"201", "202", "261", "262", "551", "552", "601", "602", "641", "642"}
    consumption = {"251", "252", "291", "292", "451", "452"}
    transfers_in = {"301", "303", "305", "311", "313", "315", "321", "325"}
    transfers_out = {"302", "304", "306", "312", "314", "316", "322", "326"}
    adjustments = {"701", "702", "711", "712", "551", "552"}

    if mvt in receipts:
        return "RECEIPT"
    if mvt in issues:
        return "ISSUE"
    if mvt in consumption:
        return "CONSUMPTION"
    if mvt in transfers_in:
        return "TRANSFER_IN"
    if mvt in transfers_out:
        return "TRANSFER_OUT"
    if mvt in adjustments:
        return "ADJUSTMENT"
    return "OTHER"


# --------------------------------------------------------------------------- #
# Tool 4: discover_s4_services (diagnostic)                                    #
# --------------------------------------------------------------------------- #

class ServiceCatalogInput(BaseModel):
    filter_term: str = Field(default="", description="Optional keyword to filter service names")


async def _discover_s4_services(filter_term: str = "") -> str:
    """Query the SAP OData service catalog and metadata to discover available services and their entity sets."""
    try:
        # First get catalog services
        data = await _s4_get(
            "/sap/opu/odata/IWFND/CATALOGSERVICE;v=2/ServiceCollection",
            params={"$format": "json", "$top": "500"},
        )
        services = _fmt_odata(data)
        result = []
        for svc in services:
            # CATALOGSERVICE v2 uses TechnicalServiceName (not TechnicalName)
            name = (svc.get("TechnicalServiceName")
                    or svc.get("TechnicalName")
                    or svc.get("ServiceName")
                    or svc.get("Title")
                    or "")
            title = svc.get("Title", svc.get("Description", ""))
            namespace = svc.get("Namespace", "")
            if filter_term and filter_term.lower() not in name.lower() and filter_term.lower() not in title.lower():
                continue
            result.append({"TechnicalServiceName": name, "Title": title, "Namespace": namespace})

        # Also probe metadata for known 403 services to get entity set names
        metadata_hints = []
        for svc_path in ["/sap/opu/odata/sap/OGS_MATERIAL_STOCK_SRV",
                         "/sap/opu/odata/sap/OGS_MATERIAL_DOCUMENT_SRV",
                         "/sap/opu/odata/sap/ZC_STOCKQUANTITYVALUEBYTYPE_CDS"]:
            if filter_term and filter_term.lower() not in svc_path.lower():
                continue
            try:
                meta = await _s4_get(f"{svc_path}/$metadata", params={})
                # Extract EntitySet names from raw EDMX XML
                import re
                entity_sets = re.findall(r'EntitySet[^>]+Name="([^"]+)"', meta if isinstance(meta, str) else "")
                metadata_hints.append({"service": svc_path, "entity_sets": entity_sets})
            except Exception as me:
                metadata_hints.append({"service": svc_path, "metadata_error": str(me)[:100]})

        return json.dumps({"status": "ok", "services": result[:50], "count": len(result),
                           "metadata_hints": metadata_hints})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# --------------------------------------------------------------------------- #
# Tool 5: get_plant_stock (all materials in a plant)                           #
# --------------------------------------------------------------------------- #

class PlantStockInput(BaseModel):
    plant: str = Field(description="SAP plant code, e.g. '1000'")
    min_quantity: float = Field(default=0.0, description="Only return materials with stock above this quantity (default 0 = all)")


async def _get_plant_stock(plant: str, min_quantity: float = 0.0) -> str:
    """Fetch all material stocks for a plant — tries multiple OData service paths."""
    tried: list[str] = []
    for svc_path, entity in _STOCK_PATHS:
        path_desc = f"{svc_path}/{entity}"
        tried.append(path_desc)
        try:
            data = await _s4_get(
                f"{svc_path}/{entity}",
                params={
                    "$filter": f"Plant eq '{plant}'",
                    "$format": "json",
                    "$top": "500",
                },
            )
            rows = _fmt_odata(data)
            result = []
            for r in rows:
                # Try various field names across OData versions
                qty_raw = (r.get("MatlWrhsStkQtyInMatlBaseUnit")
                           or r.get("UnrestrictedStock")
                           or r.get("Labst")
                           or r.get("StockQuantity")
                           or "0")
                try:
                    qty = float(qty_raw)
                except (TypeError, ValueError):
                    qty = 0.0
                if qty > min_quantity:
                    result.append({
                        "Material": r.get("Material", r.get("Matnr", "")),
                        "Plant": r.get("Plant", r.get("Werks", "")),
                        "StorageLocation": r.get("StorageLocation", r.get("Lgort", "")),
                        "StockQty": qty,
                        "Unit": r.get("MaterialBaseUnit", r.get("Meins", r.get("BaseUnit", ""))),
                    })
            return json.dumps({"status": "ok", "service": path_desc, "plant": plant,
                               "materials": result, "count": len(result)})

        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 404):
                logger.info("Service %s returned %s — trying next path", path_desc, e.response.status_code)
                tried.append(f"{path_desc} [HTTP {e.response.status_code}]")
                continue
            return json.dumps({"status": "error", "service": path_desc, "code": e.response.status_code, "message": str(e)})
        except Exception as e:
            tried.append(f"{path_desc} [error: {type(e).__name__}]")
            return json.dumps({"status": "error", "service": path_desc, "message": str(e)})

    return json.dumps({"status": "error", "message": f"No accessible stock service found. Tried: {tried}"})


# --------------------------------------------------------------------------- #
# Tool 6: get_plant_movements (all movements for a plant on a date)            #
# --------------------------------------------------------------------------- #

class PlantMovementsInput(BaseModel):
    plant: str = Field(description="SAP plant code, e.g. '1000'")
    date_from: str = Field(description="Posting date from (YYYY-MM-DD)")
    date_to: str = Field(description="Posting date to (YYYY-MM-DD)")


async def _get_plant_movements(plant: str, date_from: str, date_to: str) -> str:
    """Fetch ALL goods movements for a plant over a date range — tries multiple OData service paths."""
    dt_from = f"datetime'{date_from}T00:00:00'"
    dt_to = f"datetime'{date_to}T23:59:59'"
    filters = [
        f"Plant eq '{plant}'",
        f"PostingDate ge {dt_from}",
        f"PostingDate le {dt_to}",
    ]
    tried: list[str] = []
    for svc_path, entity in _MOVEMENT_PATHS:
        path_desc = f"{svc_path}/{entity}"
        tried.append(path_desc)
        try:
            data = await _s4_get(
                f"{svc_path}/{entity}",
                params={
                    "$filter": " and ".join(filters),
                    "$format": "json",
                    "$top": "500",
                },
            )
            rows = _fmt_odata(data)
            result = []
            for r in rows:
                result.append({
                    "MaterialDocument": r.get("MaterialDocument", r.get("Mblnr", "")),
                    "Item": r.get("MaterialDocumentItem", r.get("Zeile", "")),
                    "PostingDate": r.get("PostingDate", r.get("Budat", "")),
                    "Material": r.get("Material", r.get("Matnr", "")),
                    "GoodsMovementType": r.get("GoodsMovementType", r.get("Bwart", "")),
                    "Quantity": r.get("QuantityInBaseUnit", r.get("Menge", "0")),
                    "Unit": r.get("BaseUnit", r.get("Meins", "")),
                    "StorageLocation": r.get("StorageLocation", r.get("Lgort", "")),
                })
            return json.dumps({"status": "ok", "service": path_desc, "plant": plant,
                               "records": result, "count": len(result)})

        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 404):
                logger.info("Service %s returned %s — trying next path", path_desc, e.response.status_code)
                continue
            return json.dumps({"status": "error", "service": path_desc, "code": e.response.status_code, "message": str(e)})
        except Exception as e:
            return json.dumps({"status": "error", "service": path_desc, "message": str(e)})

    return json.dumps({"status": "error", "message": f"No accessible movement service found. Tried: {tried}"})


# --------------------------------------------------------------------------- #
# Build tool list                                                               #
# --------------------------------------------------------------------------- #

def get_s4_direct_tools() -> list:
    """Return LangChain tools for direct S/4HANA OData access."""
    return [
        StructuredTool(
            name="s4_get_plant_stock",
            description=(
                "Get current stock for ALL materials in a plant from SAP S/4HANA. "
                "USE THIS FIRST when running mass balance for a plant — it discovers every material "
                "with stock without needing a material number upfront."
            ),
            args_schema=PlantStockInput,
            coroutine=_get_plant_stock,
            handle_tool_error=True,
        ),
        StructuredTool(
            name="s4_get_plant_movements",
            description=(
                "Get ALL goods movements for a plant over a date range from SAP S/4HANA. "
                "USE THIS when running daily mass balance — fetches every movement across all materials "
                "for the period without needing a material number upfront."
            ),
            args_schema=PlantMovementsInput,
            coroutine=_get_plant_movements,
            handle_tool_error=True,
        ),
        StructuredTool(
            name="s4_get_material_stock",
            description=(
                "Get current stock for a specific material in a plant from SAP S/4HANA. "
                "Use when you already know the material number."
            ),
            args_schema=MaterialStockInput,
            coroutine=_get_material_stock,
            handle_tool_error=True,
        ),
        StructuredTool(
            name="s4_get_material_documents",
            description=(
                "Get goods movements for a specific material and plant over a date range. "
                "Use when you already know the material number."
            ),
            args_schema=MaterialDocumentsInput,
            coroutine=_get_material_documents,
            handle_tool_error=True,
        ),
        StructuredTool(
            name="s4_run_mass_balance",
            description=(
                "Run the full mass balance calculation for one material and plant over a date range. "
                "Fetches live stock and movements from SAP S/4HANA, calculates: "
                "Closing = Opening + Receipts - Issues - Consumption ± Transfers ± Adjustments, "
                "and classifies any variance as INFO/ADVISORY/WARNING/CRITICAL."
            ),
            args_schema=MassBalanceInput,
            coroutine=_run_mass_balance,
            handle_tool_error=True,
        ),
        StructuredTool(
            name="s4_discover_services",
            description=(
                "Query the SAP OData service catalog to discover all available services in the S/4HANA system. "
                "Use when unsure what APIs are available or to find IS-Oil & Gas specific service names."
            ),
            args_schema=ServiceCatalogInput,
            coroutine=_discover_s4_services,
            handle_tool_error=True,
        ),
    ]
