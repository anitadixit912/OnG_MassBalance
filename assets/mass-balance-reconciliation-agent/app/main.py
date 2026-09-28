import logging
import os
import uuid

import click
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from agent_executor import AgentExecutor
from mcp_providers.agw import set_user_token, reset_user_token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "5000"))

_CHAT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mass Balance Reconciliation Agent</title>
<script src="https://cdn.jsdelivr.net/npm/marked@9/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/dompurify@3/dist/purify.min.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; height: 100vh; display: flex; flex-direction: column; }
  header { background: #003366; color: #fff; padding: 12px 24px; display: flex; align-items: center; gap: 12px; }
  header h1 { font-size: 1.1rem; font-weight: 600; flex: 1; }
  header span.badge { font-size: 0.75rem; background: #0070d2; padding: 2px 8px; border-radius: 12px; }
  #token-status { font-size: 0.78rem; cursor: pointer; padding: 3px 10px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.4); }
  #token-status.ok { background: #1a7f3c; border-color: #1a7f3c; }
  #token-status.missing { background: #555; border-color: #555; }
  .token-panel { background: #fff8e1; border-bottom: 2px solid #ffc107; padding: 10px 24px; display: flex; align-items: center; gap: 10px; font-size: 0.85rem; }
  .token-panel.hidden { display: none; }
  .token-panel code { background: #fffde7; border: 1px solid #ffc107; padding: 1px 6px; border-radius: 3px; font-size: 0.82rem; }
  .token-panel input { flex: 1; padding: 7px 10px; border: 1px solid #ccc; border-radius: 4px; font-size: 0.82rem; font-family: monospace; }
  .token-panel button { padding: 6px 14px; background: #003366; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 0.82rem; white-space: nowrap; }
  .samples { background: #eef4fb; border-bottom: 1px solid #c8ddf5; padding: 8px 24px; display: flex; gap: 8px; flex-wrap: wrap; }
  .samples label { font-size: 0.75rem; color: #555; align-self: center; white-space: nowrap; }
  .sample-btn { padding: 5px 12px; background: #fff; border: 1px solid #0070d2; border-radius: 16px; color: #0070d2; font-size: 0.78rem; cursor: pointer; white-space: nowrap; }
  .sample-btn:hover { background: #0070d2; color: #fff; }
  .chat { flex: 1; overflow-y: auto; padding: 16px 24px; display: flex; flex-direction: column; gap: 12px; }
  .msg { max-width: 82%; padding: 12px 16px; border-radius: 8px; font-size: 0.9rem; line-height: 1.6; word-break: break-word; }
  .msg.user { align-self: flex-end; background: #0070d2; color: #fff; white-space: pre-wrap; }
  .msg.agent { align-self: flex-start; background: #fff; border: 1px solid #ddd; color: #222; }
  .msg.error { align-self: flex-start; background: #fff0f0; border: 1px solid #fcc; color: #c00; white-space: pre-wrap; }
  .msg.thinking { align-self: flex-start; background: #f5f5f5; border: 1px dashed #ccc; color: #888; font-style: italic; }
  /* Markdown styles inside .msg.agent */
  .msg.agent h1,.msg.agent h2,.msg.agent h3 { margin: 10px 0 6px; font-weight: 700; line-height: 1.3; }
  .msg.agent h1 { font-size: 1.2em; border-bottom: 1px solid #eee; padding-bottom: 4px; }
  .msg.agent h2 { font-size: 1.05em; }
  .msg.agent h3 { font-size: 0.95em; }
  .msg.agent p { margin: 6px 0; }
  .msg.agent ul,.msg.agent ol { margin: 6px 0 6px 20px; }
  .msg.agent li { margin: 3px 0; }
  .msg.agent strong { font-weight: 700; }
  .msg.agent em { font-style: italic; }
  .msg.agent code { background: #f4f4f4; border: 1px solid #ddd; border-radius: 3px; padding: 1px 5px; font-family: monospace; font-size: 0.88em; }
  .msg.agent pre { background: #f4f4f4; border: 1px solid #ddd; border-radius: 4px; padding: 10px; overflow-x: auto; margin: 8px 0; }
  .msg.agent pre code { background: none; border: none; padding: 0; }
  .msg.agent table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 0.88em; }
  .msg.agent th { background: #003366; color: #fff; padding: 6px 10px; text-align: left; }
  .msg.agent td { border: 1px solid #ddd; padding: 5px 10px; }
  .msg.agent tr:nth-child(even) td { background: #f9f9f9; }
  .msg.agent blockquote { border-left: 3px solid #0070d2; margin: 8px 0; padding: 4px 12px; color: #555; background: #f5f8ff; }
  .msg.agent hr { border: none; border-top: 1px solid #eee; margin: 10px 0; }
  .input-row { background: #fff; border-top: 1px solid #ddd; padding: 12px 24px; display: flex; gap: 10px; }
  .input-row textarea { flex: 1; padding: 10px; border: 1px solid #ccc; border-radius: 6px; resize: none; font-size: 0.9rem; font-family: inherit; height: 60px; }
  .input-row button { padding: 0 20px; background: #003366; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 0.95rem; font-weight: 600; }
  .input-row button:disabled { background: #999; cursor: not-allowed; }
  .context-id { font-size: 0.7rem; color: #888; text-align: center; padding: 4px; }
</style>
</head>
<body>
<header>
  <h1>&#9878;&#65039; Mass Balance Reconciliation Agent</h1>
  <span class="badge">OGS/IS-Oil AI</span>
  <span id="token-status" class="missing" onclick="toggleTokenPanel()" title="Set CF token for live SAP data">&#128274;</span>
</header>

<div class="token-panel hidden" id="token-panel">
  <strong>Optional:</strong>
  Run <code>cf oauth-token</code> in a terminal, paste below, click Save to enable live SAP data.
  <input type="password" id="token-input" placeholder="Paste CF oauth-token here…" />
  <button onclick="saveToken()">Save &amp; Connect</button>
  <button onclick="clearToken()" style="background:#888">Clear</button>
</div>

<div class="samples">
  <label>Try:</label>
  <button class="sample-btn" onclick="ask('Run daily mass balance for plant 1000 for today')">Run daily mass balance for plant 1000</button>
  <button class="sample-btn" onclick="ask('Show all CRITICAL exceptions for this month')">Show CRITICAL exceptions</button>
  <button class="sample-btn" onclick="ask('What is the closing stock for material CRUDE01 in plant 1000?')">Closing stock CRUDE01</button>
  <button class="sample-btn" onclick="ask('List all pending approval corrections')">Pending corrections</button>
  <button class="sample-btn" onclick="ask('Explain the variance classification rules')">Variance rules</button>
</div>

<div class="chat" id="chat">
  <div class="msg agent">Hello! I am the <strong>Mass Balance Reconciliation Agent</strong>.<br><br>
I automate the daily and monthly hydrocarbon mass balance reconciliation cycle — pulling live data from SAP IS-Oil &amp; Gas (OGS_S4), validating, calculating variances, and raising exceptions for your approval.<br><br>
Click a sample question above or type your own below.</div>
</div>
<div class="context-id">Session: <span id="ctx-id"></span></div>
<div class="input-row">
  <textarea id="input" placeholder="Ask the agent to run mass balance, show exceptions, approve corrections…" onkeydown="handleKey(event)"></textarea>
  <button id="send-btn" onclick="sendMessage()">Send</button>
</div>
<script>
  const LS_KEY = 'mb_agent_cf_token';
  const contextId = 'ctx-' + Math.random().toString(36).slice(2, 10);
  document.getElementById('ctx-id').textContent = contextId;

  marked.setOptions({ breaks: true, gfm: true });

  function loadToken() {
    const t = localStorage.getItem(LS_KEY) || '';
    if (t) {
      document.getElementById('token-status').textContent = '\\u2705 Token set';
      document.getElementById('token-status').className = 'ok';
    } else {
      document.getElementById('token-status').textContent = '\\u{1F512}';
      document.getElementById('token-status').className = 'missing';
    }
    return t;
  }

  function saveToken() {
    const raw = document.getElementById('token-input').value.trim();
    const t = raw.replace(/^bearer /i, '');
    if (!t) return;
    localStorage.setItem(LS_KEY, t);
    document.getElementById('token-input').value = '';
    loadToken();
    document.getElementById('token-panel').className = 'token-panel hidden';
    addAgentMsg('\\u2705 Token saved. Live SAP data is now enabled.');
  }

  function clearToken() {
    localStorage.removeItem(LS_KEY);
    loadToken();
  }

  function toggleTokenPanel() {
    const p = document.getElementById('token-panel');
    p.className = p.className.includes('hidden') ? 'token-panel' : 'token-panel hidden';
  }

  loadToken();

  function ask(text) { document.getElementById('input').value = text; sendMessage(); }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  }

  function addMsg(cls, text) {
    const div = document.createElement('div');
    div.className = 'msg ' + cls;
    div.textContent = text;
    const chat = document.getElementById('chat');
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
    return div;
  }

  function addAgentMsg(markdown) {
    const div = document.createElement('div');
    div.className = 'msg agent';
    div.innerHTML = DOMPurify.sanitize(marked.parse(markdown));
    const chat = document.getElementById('chat');
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
    return div;
  }

  async function sendMessage() {
    const inp = document.getElementById('input');
    const btn = document.getElementById('send-btn');
    const text = inp.value.trim();
    if (!text) return;

    const token = loadToken();
    inp.value = '';
    btn.disabled = true;
    addMsg('user', text);
    const thinking = addMsg('thinking', '\\u23F3 Processing…');

    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = 'Bearer ' + token;

    try {
      const res = await fetch('/', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          jsonrpc: '2.0', id: 'msg-' + Date.now(), method: 'message/send',
          params: { message: {
            messageId: 'mid-' + Date.now(), role: 'user',
            parts: [{ kind: 'text', text }]
          }, contextId }
        })
      });
      const data = await res.json();
      thinking.remove();
      const arts = data?.result?.artifacts;
      const reply = arts?.[0]?.parts?.[0]?.text || data?.error?.message || JSON.stringify(data);
      addAgentMsg(reply);
    } catch (e) {
      thinking.remove();
      addMsg('error', '\\u274C Request failed: ' + e.message);
    } finally {
      btn.disabled = false;
      inp.focus();
    }
  }
</script>
</body>
</html>"""


async def chat_ui(request: Request):
    return HTMLResponse(_CHAT_HTML)


@click.command()
@click.option("--host", default=HOST)
@click.option("--port", default=PORT)
def main(host: str, port: int):
    skill = AgentSkill(
        id="mass-balance-reconciliation-agent",
        name="mass-balance-reconciliation-agent",
        description="AI agent for refinery mass balance reconciliation using live SAP S/4HANA data via OGS_S4 destination",
        tags=["mass", "balance", "reconciliation", "agent"],
        examples=[
            "Run daily mass balance for plant 1000 for today",
            "Show all CRITICAL exceptions for this month",
        ],
    )
    agent_card = AgentCard(
        name="Mass Balance Reconciliation Agent",
        description="AI agent for refinery mass balance reconciliation using live SAP S/4HANA data via OGS_S4 destination. Covers TANK, MAT, MOV, PHYS, BOOK domains with human approval gates.",
        url=os.environ.get("AGENT_PUBLIC_URL", f"http://{host}:{port}/"),
        version="1.0.0",
        default_input_modes=["text", "text/plain"],
        default_output_modes=["text", "text/plain"],
        capabilities=AgentCapabilities(streaming=True, push_notifications=False),
        skills=[skill],
    )
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=DefaultRequestHandler(
            agent_executor=AgentExecutor(),
            task_store=InMemoryTaskStore(),
        ),
    )
    app = server.build()

    # Mount the chat UI at GET /ui
    from starlette.routing import Mount
    app.routes.insert(0, Route("/ui", endpoint=chat_ui, methods=["GET"]))

    class JWTContextMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            auth_header = request.headers.get("authorization", "")
            token = auth_header[7:] if auth_header.lower().startswith("bearer ") else None
            token_ctx = set_user_token(token)
            try:
                return await call_next(request)
            finally:
                reset_user_token(token_ctx)

    app.add_middleware(JWTContextMiddleware)

    logger.info(f"Starting Mass Balance Reconciliation Agent at http://{host}:{port}")
    logger.info(f"Chat UI available at http://{host}:{port}/ui")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
