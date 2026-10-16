'use strict';

/**
 * Inline Mass Balance Agent — calls Claude via SAP AI Core directly.
 * Replaces the external Python orchestrator A2A call.
 * Uses the 'aicore' BTP destination (same proj-vector-destination-service binding).
 */
const { resolveDestination } = require('./dest-client');
const {
    getMaterialStock,
    getMaterialDocuments,
    getPhysicalInventory,
    getProcessOrderConfirmations,
    getStockTransportOrders
} = require('./s4-client');

const DEPLOYMENT_ID    = process.env.AICORE_DEPLOYMENT_ID    || 'd20b9095bde7c0ef';
const RESOURCE_GROUP   = process.env.AICORE_RESOURCE_GROUP   || 'default';
const MODEL            = process.env.AICORE_MODEL             || 'anthropic--claude-4.5-sonnet';

// Per-context in-memory chat history (contextId → messages[])
const _history = new Map();

function _getHistory(contextId) {
    if (!_history.has(contextId)) _history.set(contextId, []);
    return _history.get(contextId);
}

// ── AI Core Claude call ────────────────────────────────────────────────────
// Claude (Anthropic) deployments on AI Core use /invoke with the Anthropic
// Messages API body — NOT the OpenAI /chat/completions subpath.

async function _callClaude(systemPrompt, messages) {
    const { url, headers } = await resolveDestination('aicore');
    const endpoint = `${url}/v2/inference/deployments/${DEPLOYMENT_ID}/invoke`;

    const body = JSON.stringify({
        anthropic_version: 'bedrock-2023-05-31',
        max_tokens       : 4096,
        temperature      : 0,
        system           : systemPrompt,
        messages
    });

    const res = await fetch(endpoint, {
        method : 'POST',
        headers: {
            'Content-Type'      : 'application/json',
            'AI-Resource-Group' : RESOURCE_GROUP,
            ...headers
        },
        body
    });

    if (!res.ok) {
        const err = await res.text();
        throw new Error(`AI Core HTTP ${res.status}: ${err}`);
    }

    const data = await res.json();
    // Anthropic Messages API: content[0].text
    // Fallback for any wrapper formats
    return data?.content?.[0]?.text
        ?? data?.choices?.[0]?.message?.content
        ?? JSON.stringify(data);
}

// ── System prompt ──────────────────────────────────────────────────────────

const SYSTEM_PROMPT = `You are the Mass Balance Reconciliation Agent for a refinery hydrocarbon mass balance system.
You execute the full reconciliation pipeline yourself using the SAP data provided to you.

## Pipeline (execute in this exact order when given data)

### Step 1 — Validate the data package
All 6 domains must have ≥1 record: TANK, MAT, MOV, PHYS, BOOK, TRANSFERS.
If any domain is empty → FAIL. HALT. Report which domain failed.
Also check: material numbers in MOV exist in TANK, PHYS items reference valid plant/storage.
Flag quantities deviating >3 standard deviations from period average.
On PASS log: M2.achieved: VALIDATION_ENGINE_OPERATIONAL
On FAIL log: M2.missed: VALIDATION_FAILED — then STOP.

### Step 2 — Calculate mass balance
Formula: Closing = Opening + Receipts − Issues − Consumption ± Transfers ± Adjustments
- Opening = MatlWrhsStkQtyInMatlBaseUnit from TANK (start of period)
- Receipts = MOV items with GoodsMovementType in [101, 501]
- Issues = MOV items with GoodsMovementType in [201, 261, 601]
- Consumption = ConfirmationYieldQuantity from BOOK
- Transfers = OrderQuantity from TRANSFERS
- Adjustments = (Quantity − BookQtyBfrCountInMatlBaseUnit) from PHYS
Calculate at Plant, Tank/StorageLocation, and Material level.
Compute: variance_MT = physical_stock_MT − book_stock_MT, variance_pct = variance_MT / book_stock_MT.
On success log: M3.achieved: MASS_BALANCE_CALCULATION_VALIDATED

### Step 3 — Classify exceptions
Tolerance matrix:
- INFO: variance < 0.1% AND < 1 MT
- ADVISORY: 0.1–0.5% OR 1–5 MT
- WARNING: 0.5–2.0% OR 5–20 MT
- CRITICAL: > 2.0% OR > 20 MT
Root causes: MC (meter calibration), TX (transaction error), MD (missing document), TF (transfer in transit), PL (process loss), SY (system error).
Exception ID format: EXC-{YYYY-MM}-{NNNN}. All exceptions status = OPEN.
On success log: M4.achieved: VARIANCE_EXCEPTION_PIPELINE_ACTIVE

### Step 4 — Present report and approval gate
Executive KPI Summary first:
- Overall variance %, exception counts (CRITICAL/WARNING/ADVISORY/INFO), pending approvals, reconciled count
Exception table (CRITICAL first): Exception ID · Period · Plant · Tank · Material · Variance MT · Variance % · Severity · Root Cause · Recommendation · Status

For CRITICAL or WARNING exceptions with a proposed correction:
1. Ask: "Do you approve posting this correction? Please confirm with your name and role."
2. WAIT for explicit named-user confirmation
3. NEVER auto-post — no SAP document created without approval
4. On approval log: M5.achieved: HUMAN_APPROVAL_GATES_DEPLOYED
5. On bypass: M5.missed: APPROVAL_GATE_BYPASSED — CRITICAL ALERT

## Critical Rules
- NEVER auto-post SAP corrections
- NEVER fabricate data — use only the data provided in <sap_data>. If a domain array is empty, report it as missing — do NOT invent quantities.
- If you receive <sap_data_error>, report the error to the user verbatim. Do NOT attempt a calculation.
- Pipeline halts on validation failure
- For general questions (not a reconciliation run), answer directly from context`;

// ── Data collection ────────────────────────────────────────────────────────

async function _collectData(plant, period) {
    const [year, month] = period.split('-');
    const dateFrom = `${year}-${month}-01`;
    const dateTo   = `${year}-${month}-${new Date(+year, +month, 0).getDate()}`;

    const [tank, mov, phys, book, transfers] = await Promise.allSettled([
        getMaterialStock(plant),
        getMaterialDocuments(plant, dateFrom, dateTo),
        getPhysicalInventory(plant, year),
        getProcessOrderConfirmations(plant, dateFrom, dateTo),
        getStockTransportOrders(plant, dateFrom, dateTo)
    ]);

    return {
        TANK     : tank.status      === 'fulfilled' ? tank.value      : [],
        MOV      : mov.status       === 'fulfilled' ? mov.value       : [],
        PHYS     : phys.status      === 'fulfilled' ? phys.value      : [],
        BOOK     : book.status      === 'fulfilled' ? book.value      : [],
        TRANSFERS: transfers.status === 'fulfilled' ? transfers.value : [],
        _errors  : {
            TANK     : tank.status      === 'rejected' ? tank.reason.message      : null,
            MOV      : mov.status       === 'rejected' ? mov.reason.message       : null,
            PHYS     : phys.status      === 'rejected' ? phys.reason.message      : null,
            BOOK     : book.status      === 'rejected' ? book.reason.message      : null,
            TRANSFERS: transfers.status === 'rejected' ? transfers.reason.message : null,
        }
    };
}

// ── Public API ─────────────────────────────────────────────────────────────

/**
 * Send a chat message to the inline agent.
 * For reconciliation triggers, collects live S/4 data first then passes it to Claude.
 */
async function sendAgentMessage(message, contextId) {
    const history = _getHistory(contextId);
    const isRunRequest = /run|reconcil|mass.?balance|plant\s*\d{4}/i.test(message);

    let userContent = message;

    if (isRunRequest) {
        // Extract plant and period from message
        const plantMatch  = message.match(/plant\s*[:\-]?\s*(\d{4})/i);
        const periodMatch = message.match(/(\d{4}[-/]\d{2}(?:[-/]\d{2})?)/);
        const plant  = plantMatch?.[1]  || '1000';
        const period = periodMatch?.[1]?.substring(0, 7) || new Date().toISOString().substring(0, 7);

        let data;
        try {
            data = await _collectData(plant, period);
        } catch (e) {
            data = { _collectionError: e.message };
        }

        // Hard-stop guard: if S/4 fetch failed entirely, tell Claude explicitly —
        // do NOT let it respond as if it has data.
        if (data._collectionError) {
            userContent = `${message}\n\n<sap_data_error plant="${plant}" period="${period}">\nS/4HANA data collection failed: ${data._collectionError}\nDo NOT perform any calculation or report. Tell the user the SAP system could not be reached and show the exact error.\n</sap_data_error>`;
        } else {
            // Surface any per-domain fetch errors so Claude reports them
            const domainErrors = Object.entries(data._errors || {})
                .filter(([, v]) => v)
                .map(([k, v]) => `${k}: ${v}`)
                .join('; ');
            const errorNote = domainErrors
                ? `\n<fetch_errors>${domainErrors}</fetch_errors>`
                : '';
            userContent = `${message}\n\n<sap_data plant="${plant}" period="${period}">${errorNote}\n${JSON.stringify({ ...data, _errors: undefined }, null, 2)}\n</sap_data>`;
        }
    }

    history.push({ role: 'user', content: userContent });

    const reply = await _callClaude(SYSTEM_PROMPT, history);

    history.push({ role: 'assistant', content: reply });

    // Keep history bounded to last 20 turns to avoid token overflow
    if (history.length > 40) history.splice(0, history.length - 40);

    return reply;
}

/**
 * Trigger a reconciliation run — convenience wrapper used by CAP service.
 */
async function triggerReconciliation(plant, period, contextId) {
    return sendAgentMessage(
        `Run mass balance reconciliation for plant ${plant} for period ${period}`,
        contextId
    );
}

/**
 * Notify agent of an approval/rejection decision.
 */
async function notifyApproval(exceptionId, decision, approverName, approverRole, contextId) {
    const msg = decision === 'APPROVED'
        ? `Correction for exception ${exceptionId} has been APPROVED by ${approverName} (${approverRole}). Please proceed.`
        : `Correction for exception ${exceptionId} has been REJECTED by ${approverName} (${approverRole}). Do not post.`;
    return sendAgentMessage(msg, contextId);
}

module.exports = { sendAgentMessage, triggerReconciliation, notifyApproval };
