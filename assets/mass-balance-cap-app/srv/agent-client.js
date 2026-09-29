'use strict';

// The agent is a CF app in the same BTP subaccount — its public route is
// injected via MASS_BALANCE_AGENT_URL in mta.yaml. No BTP Destination needed.
// Auth is handled by forwarding the user's XSUAA JWT (principal propagation),
// mirroring the JWTContextMiddleware already in the agent's main.py.
const AGENT_URL = (process.env.MASS_BALANCE_AGENT_URL || '').replace(/\/$/, '');

if (!AGENT_URL) {
    // Warn at startup so misconfiguration is obvious in CF logs
    console.warn('[agent-client] MASS_BALANCE_AGENT_URL is not set.');
}

/**
 * Send a message to the Mass Balance Reconciliation Agent via A2A JSON-RPC 2.0.
 * @param {string} message    User text
 * @param {string} contextId  Conversation context (stable per UI session)
 * @param {string} [userJwt]  Optional CF XSUAA JWT for principal propagation
 * @returns {Promise<string>} Agent text reply
 */
async function sendAgentMessage(message, contextId, userJwt) {
    if (!AGENT_URL) throw new Error('MASS_BALANCE_AGENT_URL is not configured.');

    const reqHeaders = { 'Content-Type': 'application/json' };
    if (userJwt) reqHeaders['Authorization'] = `Bearer ${userJwt}`;

    const body = JSON.stringify({
        jsonrpc: '2.0',
        id     : `cap-${Date.now()}`,
        method : 'message/send',
        params : {
            message: {
                messageId: `mid-${Date.now()}`,
                role     : 'user',
                parts    : [{ kind: 'text', text: message }]
            },
            contextId
        }
    });

    const res = await fetch(AGENT_URL, { method: 'POST', headers: reqHeaders, body });
    if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Agent HTTP ${res.status}: ${errText}`);
    }
    const data = await res.json();
    if (data.error) throw new Error(`Agent error: ${JSON.stringify(data.error)}`);

    const artifacts = data?.result?.artifacts || [];
    return artifacts[0]?.parts?.[0]?.text || JSON.stringify(data?.result ?? data);
}

/**
 * Trigger a mass balance reconciliation run via the agent.
 */
async function triggerReconciliation(plant, period, contextId, userJwt) {
    const message = `Run mass balance reconciliation for plant ${plant} for period ${period}`;
    return sendAgentMessage(message, contextId, userJwt);
}

/**
 * Notify the agent that a correction was approved or rejected.
 */
async function notifyApproval(exceptionId, decision, approverName, approverRole, contextId, userJwt) {
    const message = decision === 'APPROVED'
        ? `Correction for exception ${exceptionId} has been APPROVED by ${approverName} (${approverRole}). Please proceed.`
        : `Correction for exception ${exceptionId} has been REJECTED by ${approverName} (${approverRole}). Do not post.`;
    return sendAgentMessage(message, contextId, userJwt);
}

module.exports = { sendAgentMessage, triggerReconciliation, notifyApproval };
