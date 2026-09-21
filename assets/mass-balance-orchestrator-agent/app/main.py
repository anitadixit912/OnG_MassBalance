from sap_cloud_sdk.aicore import set_aicore_config
set_aicore_config()
import logging, os
import click, uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from sap_cloud_sdk import bootstrap
from starlette.middleware.base import BaseHTTPMiddleware
from agent_executor import AgentExecutor
from mcp_providers.agw import set_user_token, reset_user_token
logging.basicConfig(level=logging.INFO)
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "5000"))
@click.command()
@click.option("--host", default=HOST)
@click.option("--port", default=PORT)
def main(host, port):
    skill = AgentSkill(id="mass-balance-orchestrator-agent", name="mass-balance-orchestrator-agent", description="Orchestrates the full refinery mass balance reconciliation pipeline across 5 sub-agents.", tags=["orchestrator", "mass-balance", "reconciliation"], examples=["Run daily mass balance for plant 1000 for today", "Show all CRITICAL exceptions for this month"])
    agent_card = AgentCard(name="Mass Balance Orchestrator Agent", description="Orchestrates the full refinery mass balance reconciliation pipeline. Coordinates 5 sub-agents with human approval gates.", url=os.environ.get("AGENT_PUBLIC_URL", f"http://{host}:{port}/"), version="1.0.0", default_input_modes=["text", "text/plain"], default_output_modes=["text", "text/plain"], capabilities=AgentCapabilities(streaming=True, push_notifications=False), skills=[skill])
    server = A2AStarletteApplication(agent_card=agent_card, http_handler=DefaultRequestHandler(agent_executor=AgentExecutor(), task_store=InMemoryTaskStore()))
    app = server.build()
    class JWTContextMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            auth_header = request.headers.get("authorization", "")
            token = auth_header[7:] if auth_header.lower().startswith("bearer ") else None
            token_ctx = set_user_token(token)
            try: return await call_next(request)
            finally: reset_user_token(token_ctx)
    app.add_middleware(JWTContextMiddleware)
    bootstrap(app)
    uvicorn.run(app, host=host, port=port)
if __name__ == "__main__":
    main()
