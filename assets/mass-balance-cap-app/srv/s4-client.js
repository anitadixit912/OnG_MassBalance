'use strict';

// Base URL for local dev; overridden by BTP Destination 'OGS_S4' in production
const OGS_S4_URL = process.env.MASS_BALANCE_OGS_S4_URL || '';

/**
 * Resolve the OGS_S4 destination URL + auth headers.
 * Mirrors the Python ogs_s4.py pattern: VCAP_SERVICES → Destination Service
 * client-credentials token → OGS_S4 destination config.
 */
async function _resolveOgsS4() {
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
                `${creds.uri}/destination-configuration/v1/destinations/OGS_S4`,
                { headers: { Authorization: `Bearer ${access_token}` } }
            );
            if (!destRes.ok) continue;
            const dest = await destRes.json();
            const url = dest.destinationConfiguration?.URL || OGS_S4_URL;
            const authTokens = dest.authTokens || [];
            const extraHeaders = authTokens.length
                ? { Authorization: `${authTokens[0].type} ${authTokens[0].value}` }
                : {};
            return { url, headers: extraHeaders };
        } catch { continue; }
    }
    if (!OGS_S4_URL) throw new Error('OGS_S4 destination not configured. Set MASS_BALANCE_OGS_S4_URL for local dev.');
    return { url: OGS_S4_URL, headers: {} };
}

async function _odata(path, params = {}) {
    const { url, headers } = await _resolveOgsS4();
    const qs = new URLSearchParams({ '$format': 'json', ...params }).toString();
    const fullUrl = `${url.replace(/\/$/, '')}${path}?${qs}`;
    const res = await fetch(fullUrl, {
        headers: { Accept: 'application/json', ...headers }
    });
    if (!res.ok) throw new Error(`OGS_S4 HTTP ${res.status} for ${path}`);
    const data = await res.json();
    // Support both OData v2 (d.results) and v4 (value)
    return data?.d?.results ?? data?.value ?? data?.d ?? data;
}

/**
 * Fetch material warehouse stock for a plant (TANK / MAT domain).
 * Uses API_MATERIAL_STOCK_SRV — entity A_MatlStkInAcctMod.
 * @param {string} plant
 * @param {string} [material]
 */
async function getMaterialStock(plant, material) {
    const filter = material
        ? `Plant eq '${plant}' and Material eq '${material}'`
        : `Plant eq '${plant}'`;
    return _odata('/sap/opu/odata/sap/API_MATERIAL_STOCK_SRV/A_MatlStkInAcctMod', {
        '$filter': filter,
        '$select': 'Material,Plant,StorageLocation,Batch,MatlWrhsStkQtyInMatlBaseUnit,MaterialBaseUnit'
    });
}

/**
 * Fetch material document items for a plant and date range (MOV domain).
 * Uses API_MATERIAL_DOCUMENT_SRV — expand to items.
 * @param {string} plant
 * @param {string} dateFrom  YYYY-MM-DD
 * @param {string} dateTo    YYYY-MM-DD
 */
async function getMaterialDocuments(plant, dateFrom, dateTo) {
    const filter = `Plant eq '${plant}' and PostingDate ge datetime'${dateFrom}T00:00:00' and PostingDate le datetime'${dateTo}T23:59:59'`;
    return _odata('/sap/opu/odata/sap/API_MATERIAL_DOCUMENT_SRV/A_MaterialDocumentHeader', {
        '$filter': filter,
        '$expand': 'to_MaterialDocumentItem',
        '$select': 'MaterialDocument,MaterialDocumentYear,PostingDate,to_MaterialDocumentItem/Material,to_MaterialDocumentItem/Plant,to_MaterialDocumentItem/StorageLocation,to_MaterialDocumentItem/GoodsMovementType,to_MaterialDocumentItem/QuantityInBaseUnit,to_MaterialDocumentItem/MaterialBaseUnit'
    });
}

/**
 * Fetch physical inventory documents for a plant and fiscal year (PHYS domain).
 * Uses CE_PHYSICALINVENTORYDOCUMENT_0001 (OData v4).
 * @param {string} plant
 * @param {string} fiscalYear  e.g. '2026'
 */
async function getPhysicalInventory(plant, fiscalYear) {
    return _odata('/sap/opu/odata4/sap/api_phys_inv_doc/srvd_a2x/sap/physicalinventorydocument/0001/PhysicalInventoryDocumentItem', {
        '$filter': `Plant eq '${plant}' and FiscalYear eq '${fiscalYear}'`,
        '$select': 'PhysicalInventoryDocument,FiscalYear,PhysicalInventoryDocumentItem,Material,Plant,StorageLocation,BookQtyBfrCountInMatlBaseUnit,Quantity,MaterialBaseUnit,PhysicalInventoryItemIsCounted'
    });
}

/**
 * Fetch process order confirmations for a plant and date range (BOOK domain).
 * Uses API_PROC_ORDER_CONFIRMATION_2_SRV.
 * @param {string} plant
 * @param {string} dateFrom  YYYY-MM-DD
 * @param {string} dateTo    YYYY-MM-DD
 */
async function getProcessOrderConfirmations(plant, dateFrom, dateTo) {
    return _odata('/sap/opu/odata/sap/API_PROC_ORDER_CONFIRMATION_2_SRV/ProcOrdConf2', {
        '$filter': `Plant eq '${plant}' and PostingDate ge datetime'${dateFrom}T00:00:00' and PostingDate le datetime'${dateTo}T23:59:59'`,
        '$select': 'ConfirmationGroup,ConfirmationCount,OrderID,Material,Plant,ConfirmationYieldQuantity,ConfirmationScrapQuantity,ConfirmationUnit,PostingDate'
    });
}

/**
 * Fetch stock transport order items for a plant and date range (TRANSFERS domain).
 * Uses CE_STOCKTRANSPORTORDER_0001 (OData v4).
 * @param {string} plant  Supplying plant
 * @param {string} dateFrom  YYYY-MM-DD
 * @param {string} dateTo    YYYY-MM-DD
 */
async function getStockTransportOrders(plant, dateFrom, dateTo) {
    return _odata('/sap/opu/odata4/sap/api_stock_transport_order/srvd_a2x/sap/stocktransportorder/0001/StockTransportOrderItem', {
        '$filter': `SupplyingPlant eq '${plant}' and CreationDate ge ${dateFrom} and CreationDate le ${dateTo}`,
        '$select': 'StockTransportOrder,StockTransportOrderItem,Product,Plant,StorageLocation,OrderQuantity,OrderQuantityUnit,IssuingStorageLocation'
    });
}

/**
 * Fetch all five domains and return counts per domain.
 * @param {string} plant
 * @param {string} dateFrom  YYYY-MM-DD
 * @param {string} dateTo    YYYY-MM-DD
 * @param {string} fiscalYear  e.g. '2026'
 * @returns {Promise<Array<{domain, recordCount, status}>>}
 */
async function fetchDomainStatuses(plant, dateFrom, dateTo, fiscalYear) {
    const results = await Promise.allSettled([
        getMaterialStock(plant),
        getMaterialDocuments(plant, dateFrom, dateTo),
        getPhysicalInventory(plant, fiscalYear),
        getProcessOrderConfirmations(plant, dateFrom, dateTo),
        getStockTransportOrders(plant, dateFrom, dateTo)
    ]);

    const domains = ['TANK', 'MOV', 'PHYS', 'BOOK', 'TRANSFERS'];
    return domains.map((domain, i) => ({
        domain,
        recordCount: results[i].status === 'fulfilled' ? (results[i].value?.length ?? 0) : 0,
        status     : results[i].status === 'fulfilled'
            ? (results[i].value?.length > 0 ? 'LIVE' : 'MISSING')
            : 'MISSING',
        fetchedAt  : new Date().toISOString()
    }));
}

module.exports = {
    getMaterialStock,
    getMaterialDocuments,
    getPhysicalInventory,
    getProcessOrderConfirmations,
    getStockTransportOrders,
    fetchDomainStatuses
};
