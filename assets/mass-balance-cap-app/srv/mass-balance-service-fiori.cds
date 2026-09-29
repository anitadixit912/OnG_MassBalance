using MassBalanceService as service from './mass-balance-service';

// ═══════════════════════════════════════════════════════════════════════════════
// RECONCILIATION RUNS — KPI Dashboard (Analytical List Page)
// ═══════════════════════════════════════════════════════════════════════════════

annotate service.ReconciliationRuns with @(
    UI.HeaderInfo: {
        TypeName      : 'Reconciliation Run',
        TypeNamePlural: 'Reconciliation Runs',
        Title         : { Value: plant },
        Description   : { Value: period }
    },
    UI.PresentationVariant: {
        SortOrder      : [{ Property: startedAt, Descending: true }],
        Visualizations : ['@UI.Chart', '@UI.LineItem']
    },
    UI.Chart: {
        Title      : 'Overall Variance % — Last 10 Runs',
        ChartType  : #Bar,
        Measures   : [ overallVariancePct ],
        MeasureAttributes: [{
            Measure : overallVariancePct,
            Role    : #Axis1
        }],
        Dimensions : [ period ],
        DimensionAttributes: [{
            Dimension : period,
            Role      : #Category
        }]
    },
    UI.SelectionFields: [ plant, period, status ],
    UI.LineItem: [
        { Value: plant,              Label: 'Plant' },
        { Value: period,             Label: 'Period' },
        { Value: status,             Label: 'Status',
          Criticality: statusCriticality,
          CriticalityRepresentation: #WithIcon },
        { Value: dataCompleteness,   Label: 'Data Completeness %' },
        { Value: overallVariancePct, Label: 'Variance %' },
        { Value: tanksReconciled,    Label: 'Tanks Reconciled' },
        { Value: exceptionCount,     Label: 'Exceptions' },
        { Value: pendingApprovals,   Label: 'Pending Approvals' },
        { Value: triggeredBy,        Label: 'Triggered By' },
        { Value: startedAt,          Label: 'Started' },
        { Value: completedAt,        Label: 'Completed' }
    ],
    UI.KPIs: {
        KPI1: {
            DataPoint       : { Value: overallVariancePct, Title: 'Refinery Variance %' },
            SelectionVariant: { SelectOptions: [] }
        },
        KPI2: {
            DataPoint       : { Value: exceptionCount, Title: 'Active Exceptions' },
            SelectionVariant: { SelectOptions: [] }
        },
        KPI3: {
            DataPoint       : { Value: pendingApprovals, Title: 'Pending Approvals' },
            SelectionVariant: { SelectOptions: [] }
        },
        KPI4: {
            DataPoint       : { Value: tanksReconciled, Title: 'Tanks Reconciled' },
            SelectionVariant: { SelectOptions: [] }
        }
    },
    UI.Facets: [
        {
            $Type : 'UI.ReferenceFacet',
            Label : 'Run Details',
            Target: '@UI.FieldGroup#RunDetails'
        },
        {
            $Type : 'UI.ReferenceFacet',
            Label : 'Domain Status',
            Target: 'domainStatuses/@UI.LineItem'
        },
        {
            $Type : 'UI.ReferenceFacet',
            Label : 'Agent Response',
            Target: '@UI.FieldGroup#AgentResponse'
        }
    ],
    UI.FieldGroup #RunDetails: {
        Label: 'Run Details',
        Data: [
            { Value: plant },
            { Value: period },
            { Value: status,             Criticality: statusCriticality },
            { Value: dataCompleteness },
            { Value: overallVariancePct },
            { Value: tanksReconciled },
            { Value: exceptionCount },
            { Value: pendingApprovals },
            { Value: triggeredBy },
            { Value: startedAt },
            { Value: completedAt }
        ]
    },
    UI.FieldGroup #AgentResponse: {
        Label: 'Agent Narrative',
        Data: [{ Value: agentReply, Label: 'Agent Response' }]
    }
);

// ═══════════════════════════════════════════════════════════════════════════════
// EXCEPTIONS — List Report + Object Page
// ═══════════════════════════════════════════════════════════════════════════════

annotate service.Exceptions with @(
    UI.HeaderInfo: {
        TypeName      : 'Exception',
        TypeNamePlural: 'Exceptions',
        Title         : { Value: exceptionId },
        Description   : { Value: material }
    },
    UI.SelectionFields: [ severity, plant, period, status, rootCause ],
    UI.LineItem: [
        { Value: exceptionId,      Label: 'Exception ID' },
        { Value: period,           Label: 'Period' },
        { Value: plant,            Label: 'Plant' },
        { Value: storageLocation,  Label: 'SLoc (Tank)' },
        { Value: material,         Label: 'Material' },
        { Value: varianceMT,       Label: 'Variance MT' },
        { Value: variancePct,      Label: 'Variance %' },
        {
            Value                    : severity,
            Label                    : 'Severity',
            Criticality              : severityCriticality,
            CriticalityRepresentation: #WithIcon
        },
        { Value: rootCause,        Label: 'Root Cause' },
        {
            Value                    : status,
            Label                    : 'Status',
            Criticality              : statusCriticality,
            CriticalityRepresentation: #WithIcon
        },
        { Value: recommendation,   Label: 'Recommendation' }
    ],
    UI.Facets: [
        {
            $Type : 'UI.ReferenceFacet',
            Label : 'Exception Details',
            Target: '@UI.FieldGroup#Details'
        },
        {
            $Type : 'UI.ReferenceFacet',
            Label : 'Evidence & Recommendation',
            Target: '@UI.FieldGroup#Evidence'
        },
        {
            $Type : 'UI.ReferenceFacet',
            Label : 'Approval History',
            Target: 'approvalActions/@UI.LineItem'
        }
    ],
    UI.FieldGroup #Details: {
        Label: 'Exception Details',
        Data: [
            { Value: exceptionId },
            { Value: period },
            { Value: plant },
            { Value: storageLocation },
            { Value: material },
            { Value: varianceMT },
            { Value: variancePct },
            { Value: severity,  Criticality: severityCriticality },
            { Value: rootCause },
            { Value: status,    Criticality: statusCriticality },
            { Value: createdAt }
        ]
    },
    UI.FieldGroup #Evidence: {
        Label: 'Evidence & Recommendation',
        Data: [
            { Value: supportingDocuments, Label: 'Supporting SAP Documents' },
            { Value: recommendation,      Label: 'Recommended Correction' }
        ]
    }
);

annotate service.Exceptions with {
    severity  @(
        Common.ValueListWithFixedValues: true,
        Common.ValueList: {
            CollectionPath: 'Exceptions',
            Parameters: [{ $Type: 'Common.ValueListParameterOut',
                           LocalDataProperty: severity,
                           ValueListProperty: 'severity' }]
        }
    );
    rootCause @Common.ValueListWithFixedValues: true;
    status    @Common.ValueListWithFixedValues: true;
    plant     @Common.Label: 'Plant';
    period    @Common.Label: 'Period';
}

// ═══════════════════════════════════════════════════════════════════════════════
// APPROVALS WORKFLOW — dedicated Plant Manager screen (ADVISORY/WARNING/CRITICAL
// exceptions that are OPEN or UNDER_REVIEW)
// ═══════════════════════════════════════════════════════════════════════════════

annotate service.Approvals with @(
    UI.HeaderInfo: {
        TypeName      : 'Pending Approval',
        TypeNamePlural: 'Approval Workflow',
        Title         : { Value: exceptionId },
        Description   : { Value: material }
    },
    UI.SelectionFields: [ severity, plant, period, status ],
    UI.LineItem: [
        { Value: exceptionId,     Label: 'Exception ID' },
        { Value: period,          Label: 'Period' },
        { Value: plant,           Label: 'Plant' },
        { Value: storageLocation, Label: 'SLoc (Tank)' },
        { Value: material,        Label: 'Material' },
        { Value: varianceMT,      Label: 'Variance MT' },
        { Value: variancePct,     Label: 'Variance %' },
        {
            Value                    : severity,
            Label                    : 'Severity',
            Criticality              : severityCriticality,
            CriticalityRepresentation: #WithIcon
        },
        { Value: rootCause,       Label: 'Root Cause' },
        {
            Value                    : status,
            Label                    : 'Status',
            Criticality              : statusCriticality,
            CriticalityRepresentation: #WithIcon
        },
        { Value: recommendation,  Label: 'Recommended Correction' }
    ],
    UI.Facets: [
        {
            $Type : 'UI.ReferenceFacet',
            Label : 'Exception Details',
            Target: '@UI.FieldGroup#ApprovalDetails'
        },
        {
            $Type : 'UI.ReferenceFacet',
            Label : 'Evidence',
            Target: '@UI.FieldGroup#ApprovalEvidence'
        }
    ],
    UI.FieldGroup #ApprovalDetails: {
        Label: 'Exception Details',
        Data: [
            { Value: exceptionId },
            { Value: period },
            { Value: plant },
            { Value: storageLocation },
            { Value: material },
            { Value: varianceMT },
            { Value: variancePct },
            { Value: severity,  Criticality: severityCriticality },
            { Value: rootCause },
            { Value: status,    Criticality: statusCriticality }
        ]
    },
    UI.FieldGroup #ApprovalEvidence: {
        Label: 'Evidence & Correction',
        Data: [
            { Value: supportingDocuments, Label: 'Supporting SAP Documents' },
            { Value: recommendation,      Label: 'Recommended Correction' }
        ]
    }
);

// ═══════════════════════════════════════════════════════════════════════════════
// APPROVAL ACTIONS — sub-table on Exception Object Page + standalone list
// ═══════════════════════════════════════════════════════════════════════════════

annotate service.ApprovalActions with @(
    UI.HeaderInfo: {
        TypeName      : 'Approval Record',
        TypeNamePlural: 'Approval Records',
        Title         : { Value: decision },
        Description   : { Value: approverName }
    },
    UI.LineItem: [
        { Value: actionTimestamp,  Label: 'Timestamp' },
        { Value: exceptionId,      Label: 'Exception ID' },
        { Value: approverName,     Label: 'Approver' },
        { Value: approverRole,     Label: 'Role' },
        {
            Value                    : decision,
            Label                    : 'Decision',
            Criticality              : decisionCriticality,
            CriticalityRepresentation: #WithIcon
        },
        { Value: comments,         Label: 'Comments / Reason' }
    ]
);

// ═══════════════════════════════════════════════════════════════════════════════
// AUDIT LOG — read-only List Report
// ═══════════════════════════════════════════════════════════════════════════════

annotate service.AuditLogs with @(
    UI.HeaderInfo: {
        TypeName      : 'Audit Log Entry',
        TypeNamePlural: 'Audit Log',
        Title         : { Value: eventType },
        Description   : { Value: username }
    },
    UI.SelectionFields: [ eventType, username, referenceId ],
    UI.LineItem: [
        { Value: logTimestamp, Label: 'Timestamp' },
        { Value: eventType,    Label: 'Event Type' },
        { Value: username,     Label: 'User' },
        { Value: role,         Label: 'Role' },
        { Value: referenceId,  Label: 'Reference ID' },
        { Value: details,      Label: 'Details' }
    ]
);

// ═══════════════════════════════════════════════════════════════════════════════
// TOLERANCE CONFIG — editable table
// ═══════════════════════════════════════════════════════════════════════════════

annotate service.ToleranceConfigs with @(
    UI.HeaderInfo: {
        TypeName      : 'Tolerance Rule',
        TypeNamePlural: 'Tolerance Configuration',
        Title         : { Value: plant },
        Description   : { Value: materialGroup }
    },
    UI.SelectionFields: [ plant, materialGroup ],
    UI.LineItem: [
        { Value: plant,               Label: 'Plant' },
        { Value: materialGroup,       Label: 'Material Group' },
        { Value: dailyTolerancePct,   Label: 'Daily Tolerance %' },
        { Value: monthlyTolerancePct, Label: 'Monthly Tolerance %' },
        { Value: escalationAction,    Label: 'Escalation Action' }
    ],
    UI.Facets: [{
        $Type : 'UI.ReferenceFacet',
        Target: '@UI.FieldGroup#TolDetails'
    }],
    UI.FieldGroup #TolDetails: {
        Label: 'Tolerance Details',
        Data: [
            { Value: plant },
            { Value: materialGroup },
            { Value: dailyTolerancePct },
            { Value: monthlyTolerancePct },
            { Value: escalationAction }
        ]
    }
);

// ═══════════════════════════════════════════════════════════════════════════════
// DOMAIN STATUS — read-only section on Run Object Page
// ═══════════════════════════════════════════════════════════════════════════════

annotate service.DomainStatuses with @(
    UI.LineItem: [
        {
            Value                    : domain,
            Label                    : 'Domain'
        },
        {
            Value                    : status,
            Label                    : 'Status',
            Criticality              : domainCriticality,
            CriticalityRepresentation: #WithIcon
        },
        { Value: recordCount, Label: 'Record Count' },
        { Value: fetchedAt,   Label: 'Last Fetched' }
    ]
);
