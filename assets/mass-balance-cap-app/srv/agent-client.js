'use strict';

const AGENT_URL = process.env.MASS_BALANCE_AGENT_URL
    || 'https://mass-balance-reconciliation-agent.cfapps.us10.hana.ondemand.com';

/**
 * Resolve the Mass Balance Agent URL + auth headers.
 * Production: reads BTP Destination Service binding from VCAP_SERVICES,
 * fetches a client-credentials token, then resolves the MASS_BALANCE_AGENT destination.
 * Local dev: falls back to MASS_BALANCE_AGENT_URL env var.
 */
async function _resolveAgentDestination() {
    let services = {};
    try { services = JSON.parse(process.env.VCAP_SERVICES || '{}'); } catch { /**/ }

    for (const svc of (services['destination'] || [])) {
        const creds = svc.credentials || {};
        if (!creds.uri || !creds.clientid) continue;
        try {
            const tokenRes = await fetch(`${creds.url}/oauth/token`, {
                method : 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body   : new URLSearchParams({
                    grant_type   : 'client_credentials',
                    client_id    : creds.clientid,
                    client_secret: creds.clientsecret
                })
            });
            const { access_token } = await tokenRes.json();

            const destRes = await fetch(
                `${creds.uri}/destination-configuration/v1/destinations/MASS_BALANCE_AGENT`,
                { headers: { Authorization: `Bearer ${access_token}` } }
            );
            if (!destRes.ok) continue;
            const dest = await destRes.json();
            const url = dest.destinationConfiguration?.URL || AGENT_URL;
            const authTokens = dest.authTokens || [];
            const extraHeaders = authTokens.length
                ? { Authorization: `${authTokens[0].type} ${authTokens[0].value}` }
                : {};
            return { url, headers: extraHeaders };
        } catch { continue; }
    }
    return { url: AGENT_URL, headers: {} };
}

/**
 * Send a message to the Mass Balance Reconciliation Agent via A2A JSON-RPC 2.0.
 * @param {string} message    User text
 * @param {string} contextId  Conversation context (stable per UI session)
 * @param {string} [userJwt]  Optional CF JWT for principal propagation
 * @returns {Promise<string>} Agent text reply
 */
async function sendAgentMessage(message, contextId, userJwt) {
    const { url, headers } = await _resolveAgentDestination();

    const reqHeaders = { 'Content-Type': 'application/json', ...headers };
    if (userJwt && !reqHeaders['Authorization']) {
        reqHeaders['Authorization'] = `Bearer ${userJwt}`;
    }

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

    const res = await fetch(url, { method: 'POST', headers: reqHeaders, body });
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
 * Constructs the natural-language command the agent expects.
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
