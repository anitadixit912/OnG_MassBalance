namespace mb;

using { cuid, managed } from '@sap/cds/common';

// ─── Exception ────────────────────────────────────────────────────────────────
// Populated by the triggerReconciliation action from agent JSON output.
// Matches exact field names from the Exception Management Agent schema.

entity Exception {
    key exceptionId        : String(20);     // EXC-YYYY-MM-NNNN
        period             : String(10);     // YYYY-MM or YYYY-MM-DD
        plant              : String(4);
        storageLocation    : String(4);
        material           : String(40);
        varianceMT         : Decimal(13, 3);
        variancePct        : Decimal(7, 4);
        severity           : String(10) enum { INFO; ADVISORY; WARNING; CRITICAL; };
        rootCause          : String(2)  enum { MC; TX; MD; TF; PL; SY; };
        supportingDocuments: LargeString;   // JSON array of SAP document numbers
        recommendation     : LargeString;
        status             : String(15) enum {
            OPEN;
            UNDER_REVIEW;
            APPROVED;
            CLOSED;
        };
        createdAt          : Timestamp;
        approvalActions    : Composition of many ApprovalAction on approvalActions.exceptionId = $self.exceptionId;
}

// ─── ApprovalAction ───────────────────────────────────────────────────────────
// Written by approveCorrection / rejectCorrection actions.

entity ApprovalAction : cuid {
        exceptionId      : String(20);
        approverName     : String(100);
        approverRole     : String(100);
        decision         : String(10) enum { APPROVED; REJECTED; };
        comments         : LargeString;
        actionTimestamp  : Timestamp;
}

// ─── AuditLog ─────────────────────────────────────────────────────────────────
// Append-only. Handler blocks DELETE and UPDATE at service layer.

entity AuditLog : cuid {
        eventType    : String(40);   // APPROVAL_RECEIVED, APPROVAL_REJECTED, PIPELINE_MILESTONE, etc.
        username     : String(100);
        role         : String(100);
        referenceId  : String(20);   // exceptionId or correctionId
        details      : LargeString;
        logTimestamp : Timestamp;
}

// ─── ToleranceConfig ──────────────────────────────────────────────────────────
// Operator-defined thresholds per plant + material group.
// Defaults match the slide deck illustrative values.

entity ToleranceConfig : cuid {
        plant                : String(4);
        materialGroup        : String(40);
        dailyTolerancePct    : Decimal(6, 4);   // e.g. 0.0015 = 0.15%
        monthlyTolerancePct  : Decimal(6, 4);   // e.g. 0.0008 = 0.08%
        escalationAction     : String(100);
}

// ─── ReconciliationRun ────────────────────────────────────────────────────────
// One row per triggered reconciliation run.

entity ReconciliationRun : cuid {
        plant               : String(4);
        period              : String(10);   // YYYY-MM or YYYY-MM-DD
        status              : String(10) enum { RUNNING; COMPLETE; FAILED; };
        dataCompleteness    : Decimal(5, 2);    // 0–100 %
        overallVariancePct  : Decimal(7, 4);
        tanksReconciled     : Integer;
        exceptionCount      : Integer;
        pendingApprovals    : Integer;
        startedAt           : Timestamp;
        completedAt         : Timestamp;
        triggeredBy         : String(100);
        agentReply          : LargeString;      // raw agent narrative response
        domainStatuses      : Composition of many DomainStatus on domainStatuses.runId = $self.ID;
}

// ─── DomainStatus ─────────────────────────────────────────────────────────────
// Per-run status for each of the five SAP data domains.

entity DomainStatus : cuid {
        runId       : UUID;
        domain      : String(10) enum { TANK; MAT; MOV; PHYS; BOOK; TRANSFERS; };
        recordCount : Integer;
        fetchedAt   : Timestamp;
        status      : String(10) enum { LIVE; STALE; MISSING; };
}
