'use strict';

/**
 * Shared BTP Destination Service resolver.
 * Reads the destination binding from VCAP_SERVICES, gets a client-credentials
 * token from XSUAA, then fetches the named destination config.
 *
 * Used by both s4-client.js (OGS_S4) and agent-client.js (MASS_BALANCE_AGENT).
 * Both destinations are configured in the same proj-vector-destination-service.
 *
 * @param {string} destinationName  Name of the BTP destination to resolve
 * @returns {Promise<{url: string, headers: object}>}
 */
async function resolveDestination(destinationName) {
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
            if (!tokenRes.ok) continue;
            const { access_token } = await tokenRes.json();

            const destRes = await fetch(
                `${creds.uri}/destination-configuration/v1/destinations/${destinationName}`,
                { headers: { Authorization: `Bearer ${access_token}` } }
            );
            if (!destRes.ok) continue;

            const dest = await destRes.json();
            const url = dest.destinationConfiguration?.URL;
            if (!url) continue;

            // authTokens are injected by the Destination Service for OAuth/BasicAuth destinations
            const authTokens = dest.authTokens || [];
            const extraHeaders = authTokens.length
                ? { Authorization: `${authTokens[0].type} ${authTokens[0].value}` }
                : {};

            return { url: url.replace(/\/$/, ''), headers: extraHeaders };
        } catch { continue; }
    }

    // Local dev fallback: read from env vars named <DESTINATION_NAME>_URL
    const envKey = `${destinationName.replace(/-/g, '_')}_URL`;
    const fallbackUrl = process.env[envKey] || process.env.MASS_BALANCE_OGS_S4_URL || '';
    if (!fallbackUrl) {
        throw new Error(
            `BTP Destination '${destinationName}' not found and no ${envKey} env var set. ` +
            `Ensure proj-vector-destination-service is bound and the destination is configured in BTP.`
        );
    }
    return { url: fallbackUrl.replace(/\/$/, ''), headers: {} };
}

module.exports = { resolveDestination };
