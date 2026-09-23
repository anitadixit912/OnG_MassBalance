"""
LangChain tools wrapping the CF-native OGS_S4 client.
These are injected into the agent as callable tools.
"""
import json
import logging
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from mcp_providers.ogs_s4 import get_ogs_s4_client

logger = logging.getLogger(__name__)


# ── Input Schemas ──────────────────────────────────────────────────────────

class MaterialStockInput(BaseModel):
    plant: str = Field(description="SAP Plant code e.g. '1000'")
    material: str = Field(default=None, description="Optional material number filter")

class MaterialDocumentsInput(BaseModel):
    plant: str = Field(description="SAP Plant code e.g. '1000'")
    posting_date: str = Field(description="Posting date in YYYY-MM-DD format")

class PhysicalInventoryInput(BaseModel):
    plant: str = Field(description="SAP Plant code e.g. '1000'")

class StockTransportOrderInput(BaseModel):
    supplying_plant: str = Field(description="Supplying plant code e.g. '1000'")

class ProcessOrderInput(BaseModel):
    plant: str = Field(description="SAP Plant code e.g. '1000'")


# ── Tool Functions ─────────────────────────────────────────────────────────

async def _get_material_stock(plant: str, material: str = None) -> str:
    try:
        result = await get_ogs_s4_client().get_material_stock(plant, material)
        return json.dumps(result)
    except Exception as e:
        logger.error("get_material_stock failed: %s", e)
        return json.dumps({"error": str(e)})

async def _get_material_documents(plant: str, posting_date: str) -> str:
    try:
        result = await get_ogs_s4_client().get_material_documents(plant, posting_date)
        return json.dumps(result)
    except Exception as e:
        logger.error("get_material_documents failed: %s", e)
        return json.dumps({"error": str(e)})

async def _get_physical_inventory(plant: str) -> str:
    try:
        result = await get_ogs_s4_client().get_physical_inventory_documents(plant)
        return json.dumps(result)
    except Exception as e:
        logger.error("get_physical_inventory failed: %s", e)
        return json.dumps({"error": str(e)})

async def _get_stock_transport_orders(supplying_plant: str) -> str:
    try:
        result = await get_ogs_s4_client().get_stock_transport_orders(supplying_plant)
        return json.dumps(result)
    except Exception as e:
        logger.error("get_stock_transport_orders failed: %s", e)
        return json.dumps({"error": str(e)})

async def _get_process_order_confirmations(plant: str) -> str:
    try:
        result = await get_ogs_s4_client().get_process_order_confirmations(plant)
        return json.dumps(result)
    except Exception as e:
        logger.error("get_process_order_confirmations failed: %s", e)
        return json.dumps({"error": str(e)})


# ── Tool Registry ──────────────────────────────────────────────────────────

def get_ogs_s4_tools() -> list:
    """Return all OGS_S4 tools ready for injection into the agent."""
    return [
        StructuredTool(
            name="get_material_stock",
            description="Get material stock levels from SAP IS-Oil & Gas via OGS_S4. Use for TANK and MAT data domains.",
            args_schema=MaterialStockInput,
            coroutine=_get_material_stock,
            handle_tool_error=True,
        ),
        StructuredTool(
            name="get_material_documents",
            description="Get material movement documents (MSEG/MKPF) from SAP via OGS_S4. Use for MOV data domain.",
            args_schema=MaterialDocumentsInput,
            coroutine=_get_material_documents,
            handle_tool_error=True,
        ),
        StructuredTool(
            name="get_physical_inventory_documents",
            description="Get physical inventory documents from SAP via OGS_S4. Use for PHYS data domain.",
            args_schema=PhysicalInventoryInput,
            coroutine=_get_physical_inventory,
            handle_tool_error=True,
        ),
        StructuredTool(
            name="get_stock_transport_orders",
            description="Get stock transport orders from SAP via OGS_S4. Use for TRANSFERS data domain.",
            args_schema=StockTransportOrderInput,
            coroutine=_get_stock_transport_orders,
            handle_tool_error=True,
        ),
        StructuredTool(
            name="get_process_order_confirmations",
            description="Get process order confirmations (yield/consumption) from SAP via OGS_S4. Use for BOOK data domain.",
            args_schema=ProcessOrderInput,
            coroutine=_get_process_order_confirmations,
            handle_tool_error=True,
        ),
    ]
