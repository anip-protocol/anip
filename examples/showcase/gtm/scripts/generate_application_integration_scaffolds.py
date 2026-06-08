"""Generate GTM application-integration bundles for later-phase services."""

from __future__ import annotations

import json
from pathlib import Path

from studio.server.application_integration_generation import (
    draft_application_integration_project,
    generate_application_integration_bundle,
)
from studio.server.application_integration_types import (
    ApplicationIntegrationApprovalRule,
    ApplicationIntegrationCapabilityDefinition,
    ApplicationIntegrationClarificationRule,
    ApplicationIntegrationDenialRule,
    ApplicationIntegrationFieldDefinition,
    ApplicationIntegrationGovernanceConfig,
    ApplicationIntegrationInputDefinition,
    ApplicationIntegrationObjectDefinition,
    ApplicationIntegrationPermissionRule,
    ApplicationIntegrationRestrictionRule,
    ApplicationIntegrationSafeDefaults,
    ApplicationIntegrationScenarioDefinition,
)


REPO_ROOT = Path(__file__).resolve().parents[4]
GENERATED_ROOT = REPO_ROOT / "examples" / "showcase" / "gtm" / "generated"


def build_prioritization_project():
    project = draft_application_integration_project(
        title="GTM Prioritization Service",
        summary=(
            "Governed GTM prioritization over a bounded scoring and routing backend. "
            "This service scores leads or accounts, ranks the top candidates, and "
            "previews routing without mutating downstream systems by default."
        ),
        backend_type="rest_api",
        implementation_language="python",
    )
    project.backend.systemName = "Lead Prioritization API"
    project.backend.baseUrl = "https://prioritization.internal.example.com"
    project.backend.authType = "bearer_token"
    project.backend.authNotes = (
        "Use delegated bearer auth. Keep scoring reads bounded and require explicit approval "
        "before downstream routing or assignment."
    )
    project.backend.adapterTarget = "generated-backend-template:native-api"
    project.backend.seedProfile = None

    project.objects = [
        ApplicationIntegrationObjectDefinition(
            objectId="lead",
            name="Lead",
            summary="Lead or contact candidate scored for GTM follow-up.",
            keyField="lead_id",
            fields=[
                ApplicationIntegrationFieldDefinition(fieldName="lead_id", fieldType="string", required=True, filterable=True, summary="Lead identifier."),
                ApplicationIntegrationFieldDefinition(fieldName="source", fieldType="string", filterable=True, summary="Acquisition source or channel."),
                ApplicationIntegrationFieldDefinition(fieldName="segment", fieldType="string", filterable=True, summary="Primary segment or ICP bucket."),
                ApplicationIntegrationFieldDefinition(fieldName="owner_scope", fieldType="string", filterable=True, summary="Actor-safe ownership or regional scope."),
            ],
        ),
        ApplicationIntegrationObjectDefinition(
            objectId="scorecard",
            name="Scorecard",
            summary="Explainable prioritization outcome for a bounded lead or account cohort.",
            keyField="scorecard_id",
            fields=[
                ApplicationIntegrationFieldDefinition(fieldName="priority_band", fieldType="enum", filterable=True, summary="Hot, warm, or cold."),
                ApplicationIntegrationFieldDefinition(fieldName="confidence", fieldType="number", summary="Model confidence for the prioritization outcome."),
                ApplicationIntegrationFieldDefinition(fieldName="rationale", fieldType="text", summary="Bounded reason summary."),
            ],
        ),
        ApplicationIntegrationObjectDefinition(
            objectId="routing_preview",
            name="Routing Preview",
            summary="Approval-gated routing recommendation before any mutation.",
            keyField="preview_id",
            fields=[
                ApplicationIntegrationFieldDefinition(fieldName="recommended_queue", fieldType="string", summary="Recommended target queue or team."),
                ApplicationIntegrationFieldDefinition(fieldName="action_posture", fieldType="enum", summary="Preview, approve, or deny posture."),
            ],
        ),
    ]

    project.capabilities = [
        ApplicationIntegrationCapabilityDefinition.model_validate(
            {
                "capabilityId": "gtm.score_leads",
                "title": "Score Leads",
                "summary": "Return bounded lead scores and explainable priority bands for a named cohort.",
                "objectScope": ["Lead", "Scorecard"],
                "intentType": "summarize",
                "operationType": "read",
                "sideEffectLevel": "read_only",
                "requiredInputs": [
                    {"inputName": "cohort_ref", "inputType": "string", "required": True, "summary": "Cohort reference such as inbound_last_week."}
                ],
                "optionalInputs": [
                    {"inputName": "limit", "inputType": "number", "summary": "Maximum leads to return."},
                    {"inputName": "owner_scope", "inputType": "string", "summary": "Actor-safe ownership scope."},
                ],
                "supportedFilters": ["source", "segment", "owner_scope"],
                "outputShape": "record_list",
                "backendMapping": {
                    "backendOperation": "score_leads",
                    "httpMethod": "POST",
                    "pathTemplate": "/v1/prioritization/score",
                    "requestMappingSummary": "Map the bounded cohort into the scoring API request.",
                    "responseMappingSummary": "Normalize to bounded lead scorecards without exposing raw feature vectors.",
                    "errorMappingSummary": "Map unsupported cohorts, permission failures, and model unavailability into governed outcomes.",
                },
            }
        ),
        ApplicationIntegrationCapabilityDefinition.model_validate(
            {
                "capabilityId": "gtm.prioritize_accounts",
                "title": "Prioritize Accounts",
                "summary": "Rank bounded accounts or enriched cohorts by explainable GTM priority.",
                "objectScope": ["Lead", "Scorecard"],
                "intentType": "summarize",
                "operationType": "read",
                "sideEffectLevel": "read_only",
                "requiredInputs": [
                    {"inputName": "cohort_ref", "inputType": "string", "required": True, "summary": "Account cohort or upstream GTM slice."}
                ],
                "optionalInputs": [
                    {"inputName": "ranking_basis", "inputType": "enum", "summary": "Priority ranking basis such as deal_likelihood."},
                    {"inputName": "limit", "inputType": "number", "summary": "Maximum accounts to return."},
                ],
                "supportedFilters": ["segment", "owner_scope"],
                "outputShape": "record_list",
                "backendMapping": {
                    "backendOperation": "prioritize_accounts",
                    "httpMethod": "POST",
                    "pathTemplate": "/v1/prioritization/accounts",
                    "requestMappingSummary": "Map the bounded account cohort into a prioritization request.",
                    "responseMappingSummary": "Normalize into bounded ranked accounts with explainable rationale.",
                    "errorMappingSummary": "Map ambiguous ranking basis and permission failures into governed outcomes.",
                },
            }
        ),
        ApplicationIntegrationCapabilityDefinition.model_validate(
            {
                "capabilityId": "gtm.route_leads",
                "title": "Route Leads",
                "summary": "Preview or approve routing recommendations for a bounded lead cohort.",
                "objectScope": ["Lead", "Routing Preview"],
                "intentType": "trigger_workflow",
                "operationType": "write",
                "sideEffectLevel": "approval_required_write",
                "requiredInputs": [
                    {"inputName": "cohort_ref", "inputType": "string", "required": True, "summary": "Bounded lead cohort to route."},
                    {"inputName": "target_queue", "inputType": "string", "required": True, "summary": "Target queue, team, or posture."},
                ],
                "optionalInputs": [
                    {"inputName": "owner_scope", "inputType": "string", "summary": "Actor-safe routing scope."},
                ],
                "supportedFilters": ["owner_scope"],
                "outputShape": "action_receipt",
                "backendMapping": {
                    "backendOperation": "route_leads",
                    "httpMethod": "POST",
                    "pathTemplate": "/v1/prioritization/route",
                    "requestMappingSummary": "Build a routing preview or approved routing request from bounded inputs.",
                    "responseMappingSummary": "Normalize to a preview or action receipt with approval semantics.",
                    "errorMappingSummary": "Map authority gaps, approval requirements, and unsupported targets into governed outcomes.",
                },
            }
        ),
    ]

    project.governance = ApplicationIntegrationGovernanceConfig(
        permissionRules=[
            ApplicationIntegrationPermissionRule(
                ruleId="prioritization_read_revops_sales",
                scopeType="capability",
                scopeName="gtm.score_leads",
                actorConstraint="sales_leader_or_rev_ops_or_authorized_manager",
                purposeConstraint="bounded_pipeline_and_followup_prioritization",
                allowed=True,
                summary="Allow bounded scoring reads for authorized GTM operators.",
            ),
            ApplicationIntegrationPermissionRule(
                ruleId="routing_write_authority",
                scopeType="capability",
                scopeName="gtm.route_leads",
                actorConstraint="routing_authority_actor",
                purposeConstraint="approved_operational_routing",
                allowed=True,
                summary="Only actors with routing authority can proceed to approved routing.",
            ),
        ],
        clarificationRules=[
            ApplicationIntegrationClarificationRule(
                ruleId="clarify_missing_cohort",
                triggerType="missing_required_input",
                capabilityId="gtm.score_leads",
                summary="Clarify when the requested lead or account cohort is not explicit.",
                promptHint="Which lead or account cohort should I score?",
            ),
            ApplicationIntegrationClarificationRule(
                ruleId="clarify_missing_route_target",
                triggerType="missing_required_input",
                capabilityId="gtm.route_leads",
                summary="Clarify the intended route target before routing preview.",
                promptHint="Which queue or routing target should I use?",
            ),
        ],
        restrictionRules=[
            ApplicationIntegrationRestrictionRule(
                ruleId="default_prioritization_limit",
                restrictionType="result_limit",
                capabilityId="gtm.score_leads",
                summary="Restrict prioritized result sets to a bounded list.",
                value="25",
            ),
            ApplicationIntegrationRestrictionRule(
                ruleId="hide_raw_model_features",
                restrictionType="field_projection",
                capabilityId="gtm.score_leads",
                summary="Do not expose raw model features or feature weights in normal scoring responses.",
                value="priority_band,confidence,rationale",
            ),
        ],
        denialRules=[
            ApplicationIntegrationDenialRule(
                ruleId="deny_raw_scoring_export",
                denialType="forbidden_field",
                capabilityId="gtm.score_leads",
                summary="Deny requests for raw model features, feature weights, or unconstrained export.",
            ),
            ApplicationIntegrationDenialRule(
                ruleId="deny_outreach_in_prioritization",
                denialType="unsupported_object",
                capabilityId="gtm.route_leads",
                summary="Deny outreach drafting or message-generation work in the prioritization service.",
            ),
        ],
        approvalRules=[
            ApplicationIntegrationApprovalRule(
                ruleId="approval_required_for_routing",
                capabilityId="gtm.route_leads",
                approverType="manager",
                summary="Routing mutations require explicit approval before execution.",
            )
        ],
        safeDefaults=ApplicationIntegrationSafeDefaults(
            defaultResultLimit=25,
            requireApprovalForWrites=True,
            requireClarificationOnAmbiguousRecord=True,
            dryRunBeforeWrite=True,
        ),
    )

    project.scenarios = [
        ApplicationIntegrationScenarioDefinition(
            scenarioId="score-bounded-cohort",
            title="Score bounded cohort",
            request="Score inbound leads from last week and rank the hottest 10.",
            capabilityHint="gtm.score_leads",
            expectedOutcome="available",
            expectedBackendOperation="score_leads",
            notes="Bounded cohort scoring with explainable rationale.",
        ),
        ApplicationIntegrationScenarioDefinition(
            scenarioId="clarify-missing-cohort",
            title="Clarify missing cohort",
            request="Score our latest leads.",
            capabilityHint="gtm.score_leads",
            expectedOutcome="clarification_required",
            expectedBackendOperation="score_leads",
            notes="Missing cohort should clarify before scoring.",
        ),
        ApplicationIntegrationScenarioDefinition(
            scenarioId="deny-raw-model-export",
            title="Deny raw model export",
            request="Show me every raw model feature and weight behind the lead scores.",
            capabilityHint="gtm.score_leads",
            expectedOutcome="denied",
            expectedBackendOperation="score_leads",
            notes="Raw scoring internals remain out of scope.",
        ),
        ApplicationIntegrationScenarioDefinition(
            scenarioId="approval-gated-routing",
            title="Approval-gated routing",
            request="Route the highest-priority leads to sales right now.",
            capabilityHint="gtm.route_leads",
            expectedOutcome="approval_required",
            expectedBackendOperation="route_leads",
            notes="Routing should stop at approval before mutation.",
        ),
    ]

    project.metadata.derivationSummary = (
        "GTM Phase 4 prioritization service using the generic Studio Application Integration flow over a REST backend."
    )
    return project


def build_outreach_project():
    project = draft_application_integration_project(
        title="GTM Outreach Service",
        summary=(
            "Governed GTM outreach drafting over a bounded MCP drafting backend. "
            "This service drafts messages and follow-up variants without sending them."
        ),
        backend_type="mcp_server",
        implementation_language="typescript",
    )
    project.backend.systemName = "Outreach Drafting MCP"
    project.backend.baseUrl = "mcp://gtm-outreach-drafting"
    project.backend.authType = "bearer_token"
    project.backend.authNotes = (
        "Use delegated bearer auth or session-scoped MCP transport auth. Keep the first cut "
        "draft-only and deny send or transcript-export requests."
    )
    project.backend.adapterTarget = "generated-backend-template:mcp"
    project.backend.seedProfile = None

    project.objects = [
        ApplicationIntegrationObjectDefinition(
            objectId="prospect_context",
            name="Prospect Context",
            summary="Bounded GTM target context used to condition outreach drafts.",
            keyField="target_ref",
            fields=[
                ApplicationIntegrationFieldDefinition(fieldName="target_ref", fieldType="string", required=True, filterable=True, summary="Lead or account reference."),
                ApplicationIntegrationFieldDefinition(fieldName="persona", fieldType="string", filterable=True, summary="Target persona or role."),
                ApplicationIntegrationFieldDefinition(fieldName="channel", fieldType="string", filterable=True, summary="Requested outreach channel."),
            ],
        ),
        ApplicationIntegrationObjectDefinition(
            objectId="draft_message",
            name="Draft Message",
            summary="Draft-only message output with bounded rationale and context.",
            keyField="draft_id",
            fields=[
                ApplicationIntegrationFieldDefinition(fieldName="subject", fieldType="string", summary="Draft subject or opener."),
                ApplicationIntegrationFieldDefinition(fieldName="body", fieldType="text", summary="Draft content body."),
                ApplicationIntegrationFieldDefinition(fieldName="tone", fieldType="string", summary="Requested tone or style."),
            ],
        ),
        ApplicationIntegrationObjectDefinition(
            objectId="conversation_pattern",
            name="Conversation Pattern",
            summary="Bounded content pattern or objection-response variant.",
            keyField="pattern_id",
            fields=[
                ApplicationIntegrationFieldDefinition(fieldName="pattern_type", fieldType="enum", summary="Follow-up or objection pattern type."),
                ApplicationIntegrationFieldDefinition(fieldName="rationale", fieldType="text", summary="Why the variant was chosen."),
            ],
        ),
    ]

    project.capabilities = [
        ApplicationIntegrationCapabilityDefinition.model_validate(
            {
                "capabilityId": "gtm.draft_outreach_message",
                "title": "Draft Outreach Message",
                "summary": "Draft a bounded outreach message for a selected target and explicit objective.",
                "objectScope": ["Prospect Context", "Draft Message"],
                "intentType": "summarize",
                "operationType": "read",
                "sideEffectLevel": "read_only",
                "requiredInputs": [
                    {"inputName": "target_ref", "inputType": "string", "required": True, "summary": "Lead or account reference."},
                    {"inputName": "objective", "inputType": "string", "required": True, "summary": "Message objective such as first_touch or follow_up."},
                ],
                "optionalInputs": [
                    {"inputName": "channel", "inputType": "enum", "summary": "Email, LinkedIn, or call follow-up."},
                    {"inputName": "persona", "inputType": "string", "summary": "Target persona or audience."},
                ],
                "supportedFilters": ["channel", "persona"],
                "outputShape": "summary",
                "backendMapping": {
                    "backendOperation": "draft_outreach_message",
                    "httpMethod": "CUSTOM",
                    "pathTemplate": "tool://draft_outreach_message",
                    "requestMappingSummary": "Build a bounded MCP tool request from explicit GTM context.",
                    "responseMappingSummary": "Normalize draft output without exposing raw training corpus content.",
                    "errorMappingSummary": "Map missing target context and policy failures into governed outcomes.",
                },
            }
        ),
        ApplicationIntegrationCapabilityDefinition.model_validate(
            {
                "capabilityId": "gtm.suggest_followup_content",
                "title": "Suggest Follow-Up Content",
                "summary": "Return bounded follow-up content variants for an explicit GTM target.",
                "objectScope": ["Prospect Context", "Draft Message", "Conversation Pattern"],
                "intentType": "summarize",
                "operationType": "read",
                "sideEffectLevel": "read_only",
                "requiredInputs": [
                    {"inputName": "target_ref", "inputType": "string", "required": True, "summary": "Lead or account reference."}
                ],
                "optionalInputs": [
                    {"inputName": "variant_count", "inputType": "number", "summary": "Maximum variants to return."},
                ],
                "supportedFilters": ["persona"],
                "outputShape": "record_list",
                "backendMapping": {
                    "backendOperation": "suggest_followup_content",
                    "httpMethod": "CUSTOM",
                    "pathTemplate": "tool://suggest_followup_content",
                    "requestMappingSummary": "Build a bounded MCP tool request for follow-up content from GTM context.",
                    "responseMappingSummary": "Normalize a small set of draft-only follow-up variants.",
                    "errorMappingSummary": "Map missing target context or unsupported requests into governed outcomes.",
                },
            }
        ),
        ApplicationIntegrationCapabilityDefinition.model_validate(
            {
                "capabilityId": "gtm.objection_response_variants",
                "title": "Objection Response Variants",
                "summary": "Return bounded objection-response variants for a selected competitor or concern.",
                "objectScope": ["Conversation Pattern", "Draft Message"],
                "intentType": "summarize",
                "operationType": "read",
                "sideEffectLevel": "read_only",
                "requiredInputs": [
                    {"inputName": "objection_theme", "inputType": "string", "required": True, "summary": "Named objection or competitor theme."}
                ],
                "optionalInputs": [
                    {"inputName": "target_ref", "inputType": "string", "summary": "Optional GTM target reference."},
                ],
                "supportedFilters": ["persona"],
                "outputShape": "record_list",
                "backendMapping": {
                    "backendOperation": "objection_response_variants",
                    "httpMethod": "CUSTOM",
                    "pathTemplate": "tool://objection_response_variants",
                    "requestMappingSummary": "Build a bounded MCP tool request with explicit theme and optional target context.",
                    "responseMappingSummary": "Normalize a small set of response variants with bounded rationale.",
                    "errorMappingSummary": "Map unsupported themes or policy failures into governed outcomes.",
                },
            }
        ),
    ]

    project.governance = ApplicationIntegrationGovernanceConfig(
        permissionRules=[
            ApplicationIntegrationPermissionRule(
                ruleId="draft_generation_read_access",
                scopeType="capability",
                scopeName="gtm.draft_outreach_message",
                actorConstraint="authorized_gtm_operator",
                purposeConstraint="draft_only_outreach_preparation",
                allowed=True,
                summary="Allow bounded draft generation for authorized GTM operators.",
            ),
        ],
        clarificationRules=[
            ApplicationIntegrationClarificationRule(
                ruleId="clarify_missing_target_or_objective",
                triggerType="missing_required_input",
                capabilityId="gtm.draft_outreach_message",
                summary="Clarify the target or objective before drafting outreach.",
                promptHint="Which account or lead is this for, and what is the outreach objective?",
            ),
            ApplicationIntegrationClarificationRule(
                ruleId="clarify_missing_objection_theme",
                triggerType="missing_required_input",
                capabilityId="gtm.objection_response_variants",
                summary="Clarify the objection or competitor theme before generating variants.",
                promptHint="Which objection or competitor theme should I address?",
            ),
        ],
        restrictionRules=[
            ApplicationIntegrationRestrictionRule(
                ruleId="variant_limit",
                restrictionType="result_limit",
                capabilityId="gtm.suggest_followup_content",
                summary="Restrict follow-up content variants to a small bounded list.",
                value="3",
            ),
            ApplicationIntegrationRestrictionRule(
                ruleId="hide_source_transcripts",
                restrictionType="field_projection",
                capabilityId="gtm.draft_outreach_message",
                summary="Do not expose raw source transcripts or long corpus snippets in draft responses.",
                value="draft_summary_only",
            ),
        ],
        denialRules=[
            ApplicationIntegrationDenialRule(
                ruleId="deny_send_actions",
                denialType="forbidden_mutation",
                capabilityId="gtm.draft_outreach_message",
                summary="Deny send or publish requests in the first outreach cut.",
            ),
            ApplicationIntegrationDenialRule(
                ruleId="deny_raw_transcript_export",
                denialType="forbidden_field",
                capabilityId="gtm.objection_response_variants",
                summary="Deny requests for raw conversation transcripts or training-corpus export.",
            ),
        ],
        approvalRules=[],
        safeDefaults=ApplicationIntegrationSafeDefaults(
            defaultResultLimit=3,
            requireApprovalForWrites=True,
            requireClarificationOnAmbiguousRecord=True,
            dryRunBeforeWrite=True,
        ),
    )

    project.scenarios = [
        ApplicationIntegrationScenarioDefinition(
            scenarioId="draft-first-touch",
            title="Draft first-touch outreach",
            request="Draft a first-touch email for Condax based on its GTM context.",
            capabilityHint="gtm.draft_outreach_message",
            expectedOutcome="available",
            expectedBackendOperation="draft_outreach_message",
            notes="Draft-only success path with bounded target context.",
        ),
        ApplicationIntegrationScenarioDefinition(
            scenarioId="clarify-missing-target",
            title="Clarify missing target",
            request="Draft a first-touch email for this prospect.",
            capabilityHint="gtm.draft_outreach_message",
            expectedOutcome="clarification_required",
            expectedBackendOperation="draft_outreach_message",
            notes="Missing explicit target should clarify before draft generation.",
        ),
        ApplicationIntegrationScenarioDefinition(
            scenarioId="deny-send-request",
            title="Deny send request",
            request="Send this outreach sequence now.",
            capabilityHint="gtm.draft_outreach_message",
            expectedOutcome="denied",
            expectedBackendOperation="draft_outreach_message",
            notes="The first outreach cut is draft-only.",
        ),
        ApplicationIntegrationScenarioDefinition(
            scenarioId="deny-raw-transcript-export",
            title="Deny raw transcript export",
            request="Show me the raw conversation transcripts used to draft this outreach.",
            capabilityHint="gtm.objection_response_variants",
            expectedOutcome="denied",
            expectedBackendOperation="objection_response_variants",
            notes="Raw training or transcript export is out of scope.",
        ),
    ]

    project.metadata.derivationSummary = (
        "GTM Phase 5 outreach service using the generic Studio Application Integration flow over an MCP backend."
    )
    return project


def write_application_bundle(project, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle = generate_application_integration_bundle(project)

    outputs = [
        bundle.designPacket,
        bundle.anipCapabilityScaffold,
        bundle.backendAdapterScaffold,
        bundle.scenarioPackJson,
        bundle.scenarioManifestJson,
        bundle.policyStub,
    ]
    for output in outputs:
        (output_dir / output.filename).write_text(output.content)

    (output_dir / "project-state.json").write_text(json.dumps(project.model_dump(mode="json"), indent=2))
    (output_dir / "README.md").write_text(
        "\n".join(
            [
                f"# {project.title}",
                "",
                "Generated through Studio's generic Application Integration flow.",
                "",
                f"- Backend type: `{project.backend.backendType}`",
                f"- System: `{project.backend.systemName}`",
                f"- Backend template: `{project.backend.adapterTarget}`",
                f"- Implementation language: `{project.backend.implementationLanguage}`",
                "",
                "Generated artifacts:",
                f"- `{bundle.designPacket.filename}`",
                f"- `{bundle.anipCapabilityScaffold.filename}`",
                f"- `{bundle.backendAdapterScaffold.filename}`",
                f"- `{bundle.scenarioPackJson.filename}`",
                f"- `{bundle.scenarioManifestJson.filename}`",
                f"- `{bundle.policyStub.filename}`",
                "- `project-state.json`",
            ]
        )
    )


def main() -> int:
    prioritization_dir = GENERATED_ROOT / "studio_gtm_prioritization_rest"
    outreach_dir = GENERATED_ROOT / "studio_gtm_outreach_mcp"
    write_application_bundle(build_prioritization_project(), prioritization_dir)
    write_application_bundle(build_outreach_project(), outreach_dir)
    print(
        json.dumps(
            {
                "prioritization_dir": str(prioritization_dir),
                "outreach_dir": str(outreach_dir),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
