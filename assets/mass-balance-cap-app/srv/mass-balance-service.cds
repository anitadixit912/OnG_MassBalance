using mb from '../db/schema';

service MassBalanceService @(path: '/odata/v4/mass-balance') {

    // ── Exceptions ────────────────────────────────────────────────────────────
    @Capabilities.DeleteRestrictions.Deletable: false
    entity Exceptions as select from mb.Exception {
        *,
        null as severityCriticality : Integer,
        null as statusCriticality   : Integer
    }
        actions {
            action approveCorrection(
                approverName : String(100),
                approverRole : String(100),
                comments     : String
            ) returns String;

            action rejectCorrection(
                approverName : String(100),
                approverRole : String(100),
                reason       : String
            ) returns String;
        };

    // ── Approval Actions ──────────────────────────────────────────────────────
    @readonly
    entity ApprovalActions as select from mb.ApprovalAction {
        *,
        null as decisionCriticality : Integer
    };

    // ── Audit Log ─────────────────────────────────────────────────────────────
    @readonly
    @Capabilities.DeleteRestrictions.Deletable : false
    @Capabilities.UpdateRestrictions.Updatable : false
    @Capabilities.InsertRestrictions.Insertable: false
    entity AuditLogs as projection on mb.AuditLog;

    // ── Tolerance Configuration ───────────────────────────────────────────────
    entity ToleranceConfigs as projection on mb.ToleranceConfig;

    // ── Reconciliation Runs ───────────────────────────────────────────────────
    @Capabilities.DeleteRestrictions.Deletable: false
    entity ReconciliationRuns as select from mb.ReconciliationRun {
        *,
        null as statusCriticality : Integer
    }
        actions {
            action triggerReconciliation(
                plant    : String(4),
                period   : String(10),
                contextId: String
            ) returns String;
        };

    // ── Domain Statuses ───────────────────────────────────────────────────────
    @readonly
    entity DomainStatuses as select from mb.DomainStatus {
        *,
        null as domainCriticality : Integer
    };

    // ── Agent Chat ────────────────────────────────────────────────────────────
    action sendAgentMessage(
        message  : String,
        contextId: String
    ) returns String;
}

// ── Role-based access ─────────────────────────────────────────────────────────
annotate MassBalanceService with @(requires: [
    'MassBalance.Engineer',
    'MassBalance.Manager',
    'MassBalance.Compliance'
]);

annotate MassBalanceService.ToleranceConfigs with @(requires: 'MassBalance.Engineer');
annotate MassBalanceService.AuditLogs        with @(requires: [
    'MassBalance.Compliance',
    'MassBalance.Manager'
]);
