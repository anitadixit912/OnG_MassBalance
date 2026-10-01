'use strict';

const cds = require('@sap/cds');
const { sendAgentMessage, triggerReconciliation: agentTrigger, notifyApproval } = require('./agent-client');
const { fetchDomainStatuses } = require('./s4-client');

// ── Fiori criticality constants ───────────────────────────────────────────────
// 0=neutral(grey), 1=negative(red), 2=critical(orange), 3=positive(green)

const SEV_CRIT  = { CRITICAL: 1, WARNING: 2, ADVISORY: 0, INFO: 0 };
const STAT_CRIT = { OPEN: 1, UNDER_REVIEW: 2, APPROVED: 3, CLOSED: 3 };
const DOM_CRIT  = { LIVE: 3, STALE: 2, MISSING: 1 };
const DEC_CRIT  = { APPROVED: 3, REJECTED: 1 };
const RUN_CRIT  = { COMPLETE: 3, RUNNING: 2, FAILED: 1 };

function _now() { return new Date().toISOString(); }

function _getUserJwt(req) {
    try { return req.user?.tokenInfo?.getTokenValue?.() || null; } catch { return null; }
}

module.exports = class MassBalanceService extends cds.ApplicationService {

    async init() {
        const {
            Exceptions, ApprovalActions, AuditLogs,
            DomainStatuses, ReconciliationRuns, ToleranceConfigs
        } = this.entities;

        // ── Virtual criticality fields ─────────────────────────────────────────

        this.after('READ', Exceptions, rows => {
            for (const r of [rows].flat().filter(Boolean)) {
                r.severityCriticality = SEV_CRIT[r.severity]  ?? 0;
                r.statusCriticality   = STAT_CRIT[r.status]   ?? 0;
            }
        });

        this.after('READ', ApprovalActions, rows => {
            for (const r of [rows].flat().filter(Boolean))
                r.decisionCriticality = DEC_CRIT[r.decision] ?? 0;
        });

        this.after('READ', DomainStatuses, rows => {
            for (const r of [rows].flat().filter(Boolean))
                r.domainCriticality = DOM_CRIT[r.status] ?? 0;
        });

        this.after('READ', ReconciliationRuns, rows => {
            for (const r of [rows].flat().filter(Boolean))
                r.statusCriticality = RUN_CRIT[r.status] ?? 0;
        });

        // ── Guard: AuditLog is immutable ──────────────────────────────────────

        this.before(['UPDATE', 'DELETE'], AuditLogs, () => {
            const err = new cds.error('Audit log entries are immutable and cannot be modified or deleted.');
            err.code = 405;
            throw err;
        });

        // ── ACTION: approveCorrection ─────────────────────────────────────────

        this.on('approveCorrection', Exceptions, async (req) => {
            const { approverName, approverRole, comments } = req.data;
            const exceptionId = req.params[0]?.exceptionId || req.params[0];

            if (!approverName || !approverRole)
                return req.error(400, 'approverName and approverRole are required.');

            const exc = await SELECT.one.from(Exceptions).where({ exceptionId });
            if (!exc) return req.error(404, `Exception ${exceptionId} not found.`);
            if (exc.status === 'APPROVED')
                return req.error(409, `Exception ${exceptionId} is already approved.`);
            if (exc.status === 'CLOSED')
                return req.error(409, `Exception ${exceptionId} is closed.`);

            const actionId = cds.utils.uuid();
            await INSERT.into(ApprovalActions).entries({
                ID             : actionId,
                exceptionId,
                approverName,
                approverRole,
                decision       : 'APPROVED',
                comments       : comments || '',
                actionTimestamp: _now()
            });

            await UPDATE(Exceptions).set({ status: 'APPROVED' }).where({ exceptionId });

            await INSERT.into(AuditLogs).entries({
                ID          : cds.utils.uuid(),
                eventType   : 'APPROVAL_RECEIVED',
                username    : approverName,
                role        : approverRole,
                referenceId : exceptionId,
                details     : `M5.achieved: HUMAN_APPROVAL_GATES_DEPLOYED — approver=${approverName} role=${approverRole} correction_id=${exceptionId}`,
                logTimestamp: _now()
            });

            // Notify agent (best-effort — don't fail the approval if agent is unreachable)
            try {
                const jwt = _getUserJwt(req);
                await notifyApproval(exceptionId, 'APPROVED', approverName, approverRole,
                                     `cap-approval-${exceptionId}`, jwt);
            } catch (e) {
                cds.log('agent').warn('Could not notify agent of approval:', e.message);
            }

            return `Exception ${exceptionId} approved by ${approverName} (${approverRole}).`;
        });

        // ── ACTION: rejectCorrection ──────────────────────────────────────────

        this.on('rejectCorrection', Exceptions, async (req) => {
            const { approverName, approverRole, reason } = req.data;
            const exceptionId = req.params[0]?.exceptionId || req.params[0];

            if (!approverName || !approverRole)
                return req.error(400, 'approverName and approverRole are required.');

            const exc = await SELECT.one.from(Exceptions).where({ exceptionId });
            if (!exc) return req.error(404, `Exception ${exceptionId} not found.`);

            await INSERT.into(ApprovalActions).entries({
                ID             : cds.utils.uuid(),
                exceptionId,
                approverName,
                approverRole,
                decision       : 'REJECTED',
                comments       : reason || '',
                actionTimestamp: _now()
            });

            await UPDATE(Exceptions).set({ status: 'UNDER_REVIEW' }).where({ exceptionId });

            await INSERT.into(AuditLogs).entries({
                ID          : cds.utils.uuid(),
                eventType   : 'APPROVAL_REJECTED',
                username    : approverName,
                role        : approverRole,
                referenceId : exceptionId,
                details     : `Correction rejected by ${approverName} (${approverRole}). Reason: ${reason || 'none'}`,
                logTimestamp: _now()
            });

            try {
                const jwt = _getUserJwt(req);
                await notifyApproval(exceptionId, 'REJECTED', approverName, approverRole,
                                     `cap-approval-${exceptionId}`, jwt);
            } catch (e) {
                cds.log('agent').warn('Could not notify agent of rejection:', e.message);
            }

            return `Exception ${exceptionId} rejected by ${approverName} (${approverRole}).`;
        });

        // ── ACTION: triggerReconciliation ─────────────────────────────────────

        this.on('triggerReconciliation', ReconciliationRuns, async (req) => {
            const { plant, period, contextId } = req.data;
            if (!plant || !period) return req.error(400, 'plant and period are required.');

            const runId = cds.utils.uuid();
            const startedAt = _now();
            const username = req.user?.id || 'system';

            await INSERT.into(ReconciliationRuns).entries({
                ID             : runId,
                plant,
                period,
                status         : 'RUNNING',
                triggeredBy    : username,
                startedAt,
                exceptionCount : 0,
                pendingApprovals: 0,
                tanksReconciled: 0,
                dataCompleteness: 0,
                overallVariancePct: 0
            });

            await INSERT.into(AuditLogs).entries({
                ID          : cds.utils.uuid(),
                eventType   : 'RUN_TRIGGERED',
                username,
                role        : 'MassBalance.Engineer',
                referenceId : runId,
                details     : `M1: Reconciliation run triggered for plant=${plant} period=${period}`,
                logTimestamp: startedAt
            });

            // Fetch domain statuses from live S/4HANA via OGS_S4
            const [year, month] = period.split('-');
            const dateFrom = `${year}-${month}-01`;
            const dateTo   = `${year}-${month}-${new Date(+year, +month, 0).getDate()}`;
            let domainRows = [];
            try {
                domainRows = await fetchDomainStatuses(plant, dateFrom, dateTo, year);
            } catch (e) {
                cds.log('s4').warn('Domain status fetch failed:', e.message);
            }

            for (const d of domainRows) {
                await INSERT.into(DomainStatuses).entries({
                    ID         : cds.utils.uuid(),
                    runId,
                    domain     : d.domain,
                    recordCount: d.recordCount,
                    fetchedAt  : d.fetchedAt,
                    status     : d.status
                });
            }

            const liveCount = domainRows.filter(d => d.status === 'LIVE').length;
            const completeness = domainRows.length > 0
                ? Math.round((liveCount / domainRows.length) * 100) : 0;

            // Call the agent for the full reconciliation pipeline
            let agentReply = '';
            let runStatus = 'FAILED';
            let exceptions = [];
            try {
                const jwt = _getUserJwt(req);
                agentReply = await agentTrigger(plant, period, contextId || `run-${runId}`, jwt);
                runStatus = 'COMPLETE';

                // Parse exceptions from agent reply if it contains JSON
                const jsonMatch = agentReply.match(/```json\s*([\s\S]*?)```/);
                if (jsonMatch) {
                    try {
                        const parsed = JSON.parse(jsonMatch[1]);
                        exceptions = parsed.exceptions || [];
                    } catch { /**/ }
                }
            } catch (e) {
                cds.log('agent').error('Agent reconciliation failed:', e.message);
                agentReply = `Error: ${e.message}`;
            }

            // Store exceptions returned by agent
            for (const exc of exceptions) {
                const existing = await SELECT.one.from(Exceptions)
                    .where({ exceptionId: exc.exception_id });
                if (!existing) {
                    await INSERT.into(Exceptions).entries({
                        exceptionId        : exc.exception_id,
                        period             : exc.period || period,
                        plant              : exc.plant || plant,
                        storageLocation    : exc.storage_location || '',
                        material           : exc.material || '',
                        varianceMT         : exc.variance_MT ?? 0,
                        variancePct        : exc.variance_pct ?? 0,
                        severity           : exc.severity || 'INFO',
                        rootCause          : exc.root_cause || 'SY',
                        supportingDocuments: JSON.stringify(exc.supporting_documents || []),
                        recommendation     : exc.recommendation || '',
                        status             : exc.status || 'OPEN',
                        createdAt          : _now()
                    });
                }
            }

            const pendingApprovals = exceptions.filter(
                e => ['ADVISORY', 'WARNING', 'CRITICAL'].includes(e.severity)
            ).length;

            await UPDATE(ReconciliationRuns).set({
                status             : runStatus,
                dataCompleteness   : completeness,
                exceptionCount     : exceptions.length,
                pendingApprovals,
                agentReply,
                completedAt        : _now()
            }).where({ ID: runId });

            await INSERT.into(AuditLogs).entries({
                ID          : cds.utils.uuid(),
                eventType   : runStatus === 'COMPLETE' ? 'M5.achieved: HUMAN_APPROVAL_GATES_DEPLOYED' : 'RUN_FAILED',
                username,
                role        : 'system',
                referenceId : runId,
                details     : `plant=${plant} period=${period} exceptions=${exceptions.length} completeness=${completeness}%`,
                logTimestamp: _now()
            });

            return agentReply || `Reconciliation run ${runId} ${runStatus}.`;
        });

        // ── ACTION: triggerReconciliation (unbound — from UI "Trigger Run") ──────
        // Delegates to the bound action handler above by constructing a fake run.

        this.on('triggerReconciliation', async (req) => {
            if (req.entity) return; // handled by bound handler above
            const { plant, period, contextId } = req.data;
            if (!plant || !period) return req.error(400, 'plant and period are required.');

            const runId = cds.utils.uuid();
            const startedAt = _now();
            const username = req.user?.id || 'system';

            await INSERT.into(ReconciliationRuns).entries({
                ID: runId, plant, period, status: 'RUNNING',
                triggeredBy: username, startedAt,
                exceptionCount: 0, pendingApprovals: 0,
                tanksReconciled: 0, dataCompleteness: 0, overallVariancePct: 0
            });

            await INSERT.into(AuditLogs).entries({
                ID: cds.utils.uuid(), eventType: 'RUN_TRIGGERED',
                username, role: 'MassBalance.Engineer', referenceId: runId,
                details: `M1: Reconciliation run triggered for plant=${plant} period=${period}`,
                logTimestamp: startedAt
            });

            let domainRows = [];
            try {
                const [year, month] = period.split('-');
                const dateFrom = `${year}-${month}-01`;
                const dateTo   = `${year}-${month}-${new Date(+year, +month, 0).getDate()}`;
                domainRows = await fetchDomainStatuses(plant, dateFrom, dateTo, year);
            } catch (e) { cds.log('s4').warn('Domain fetch failed:', e.message); }

            for (const d of domainRows) {
                await INSERT.into(DomainStatuses).entries({
                    ID: cds.utils.uuid(), runId,
                    domain: d.domain, recordCount: d.recordCount,
                    fetchedAt: d.fetchedAt, status: d.status
                });
            }

            const completeness = domainRows.length
                ? Math.round((domainRows.filter(d=>d.status==='LIVE').length / domainRows.length) * 100) : 0;

            let agentReply = '', runStatus = 'FAILED';
            try {
                agentReply = await agentTrigger(plant, period, contextId || `run-${runId}`, _getUserJwt(req));
                runStatus = 'COMPLETE';
            } catch (e) { agentReply = `Error: ${e.message}`; }

            await UPDATE(ReconciliationRuns).set({
                status: runStatus, dataCompleteness: completeness,
                agentReply, completedAt: _now()
            }).where({ ID: runId });

            return agentReply || `Run ${runId} ${runStatus}.`;
        });

        // ── ACTION: sendAgentMessage (Agent Chat panel) ───────────────────────

        this.on('sendAgentMessage', async (req) => {
            const { message, contextId } = req.data;
            if (!message) return req.error(400, 'message is required.');
            const jwt = _getUserJwt(req);
            return sendAgentMessage(message, contextId || 'cap-chat', jwt);
        });

        await super.init();
    }
};
