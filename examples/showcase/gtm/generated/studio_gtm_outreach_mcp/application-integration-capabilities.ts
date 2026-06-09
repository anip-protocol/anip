// Starter ANIP capability scaffold for Application Integration.
// Project: GTM Outreach Service

export const capabilities = [
  {
    name: 'gtm.draft_outreach_message',
    description: 'Draft a bounded outreach message for a selected target and explicit objective.',
    sideEffectLevel: 'read_only',
  },
  {
    name: 'gtm.suggest_followup_content',
    description: 'Return bounded follow-up content variants for an explicit GTM target.',
    sideEffectLevel: 'read_only',
  },
  {
    name: 'gtm.objection_response_variants',
    description: 'Return bounded objection-response variants for a selected competitor or concern.',
    sideEffectLevel: 'read_only',
  },
]

export async function capabilityPermissionPreflight(intent: unknown): Promise<unknown> {
  throw new Error('Implement governed preflight for capability invocation')
}

export async function executeGovernedCapability(intent: unknown): Promise<unknown> {
  throw new Error('Implement backend-specific execution after preflight and clarification')
}

export async function requestMutationApproval(intent: unknown): Promise<unknown> {
  throw new Error('Implement explicit approval handling for write capabilities')
}