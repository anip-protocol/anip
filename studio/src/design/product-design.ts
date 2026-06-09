import type { ArtifactRecord, DesignSectionSufficiencyCard, DesignSectionSufficiencyStatus } from './project-types'

export const PRODUCT_SUMMARY_ARTIFACT_TYPE = 'product_summary'
export const ACTOR_MODEL_ARTIFACT_TYPE = 'actor_model'
export const BUSINESS_AREAS_ARTIFACT_TYPE = 'business_areas'
export const PERMISSION_INTENT_ARTIFACT_TYPE = 'permission_intent'
export const NON_GOALS_ARTIFACT_TYPE = 'non_goals'
export const SUCCESS_CRITERIA_ARTIFACT_TYPE = 'success_criteria'
export const PRODUCT_DESIGN_REVISION_ARTIFACT_TYPE = 'product_design_revision'
export const ASSISTANT_SECTION_CLARIFICATIONS_ARTIFACT_TYPE = 'assistant_section_clarifications'

export type ProductDesignArtifactType =
  | typeof PRODUCT_SUMMARY_ARTIFACT_TYPE
  | typeof ACTOR_MODEL_ARTIFACT_TYPE
  | typeof BUSINESS_AREAS_ARTIFACT_TYPE
  | typeof PERMISSION_INTENT_ARTIFACT_TYPE
  | typeof NON_GOALS_ARTIFACT_TYPE
  | typeof SUCCESS_CRITERIA_ARTIFACT_TYPE

export type PersistedPmArtifactStatus = 'draft' | 'active'

export function persistedPmArtifactStatus(complete: boolean): PersistedPmArtifactStatus {
  return complete ? 'active' : 'draft'
}

export interface ProductSummaryData {
  artifact_type: typeof PRODUCT_SUMMARY_ARTIFACT_TYPE
  product_purpose: string
  business_problem: string
  business_goals: string[]
  supported_question_families: string[]
  governed_behavior_summary: string
  approval_posture_summary: string
  multi_step_composition_rules: string[]
  why_now: string
  success_outcome_summary: string
}

export interface ActorModelEntry {
  actor_id: string
  title: string
  summary: string
  visibility_expectations: string
  action_expectations: string
  approval_expectations: string
  notes: string
}

export interface ActorModelData {
  artifact_type: typeof ACTOR_MODEL_ARTIFACT_TYPE
  actors: ActorModelEntry[]
}

export interface BusinessAreaEntry {
  business_area_id: string
  label: string
  description: string
}

export interface BusinessAreasData {
  artifact_type: typeof BUSINESS_AREAS_ARTIFACT_TYPE
  entries: BusinessAreaEntry[]
}

export type PermissionIntentPosture =
  | 'allowed'
  | 'bounded'
  | 'restricted'
  | 'denied'
  | 'approval_required'

export type PermissionIntentOutcomeType =
  | 'direct_result'
  | 'bounded_result'
  | 'masked_or_restricted_result'
  | 'deny_request'
  | 'approval_stop'
  | 'clarification_required'

export interface PermissionIntentRule {
  actor_id: string
  business_area: string
  access_posture: PermissionIntentPosture
  governed_outcome_type: PermissionIntentOutcomeType | ''
  governed_outcome: string
  notes: string
  review_source?: string
}

export interface PermissionIntentData {
  artifact_type: typeof PERMISSION_INTENT_ARTIFACT_TYPE
  policy_summary: string
  rules: PermissionIntentRule[]
}

export const PERMISSION_INTENT_FALLBACK_REVIEW_SOURCE = 'studio_fallback_needs_review'
export const PERMISSION_INTENT_FALLBACK_REVIEW_NOTE = 'Studio-derived review candidate because the assistant produced a policy summary but no concrete actor-by-business-area rules.'

export interface NonGoalEntry {
  statement: string
  rationale: string
}

export interface NonGoalsData {
  artifact_type: typeof NON_GOALS_ARTIFACT_TYPE
  entries: NonGoalEntry[]
}

export type SuccessCriteriaPriority = 'high' | 'medium' | 'low'

export interface SuccessCriteriaEntry {
  statement: string
  evidence: string
  priority: SuccessCriteriaPriority
  review_method: string
}

export interface SuccessCriteriaData {
  artifact_type: typeof SUCCESS_CRITERIA_ARTIFACT_TYPE
  entries: SuccessCriteriaEntry[]
}

export type ProductDesignArtifactData =
  | ProductSummaryData
  | ActorModelData
  | BusinessAreasData
  | PermissionIntentData
  | NonGoalsData
  | SuccessCriteriaData

export interface ProductDesignStatusCard {
  key: ProductDesignArtifactType
  title: string
  complete: boolean
  detail: string
  path: string
}

export interface ProductDesignRevisionSnapshotItem {
  artifact_type: ProductDesignArtifactType
  artifact_id: string
  title: string
  content_hash: string
  updated_at: string
  data: ProductDesignArtifactData
}

export interface ProductDesignRevisionData {
  artifact_type: typeof PRODUCT_DESIGN_REVISION_ARTIFACT_TYPE
  revision_number: number
  revision_artifact_id: string
  previous_revision_artifact_id: string | null
  product_design_hash: string | null
  saved_at: string
  snapshot: ProductDesignRevisionSnapshotItem[]
}

export interface ProductDesignSufficiencyContext {
  documents_count: number
  requirements_count: number
  scenarios_count: number
}

export function makeBlankActor(): ActorModelEntry {
  return {
    actor_id: '',
    title: '',
    summary: '',
    visibility_expectations: '',
    action_expectations: '',
    approval_expectations: '',
    notes: '',
  }
}

export function makeBlankPermissionRule(): PermissionIntentRule {
  return {
    actor_id: '',
    business_area: '',
    access_posture: 'bounded',
    governed_outcome_type: '',
    governed_outcome: '',
    notes: '',
  }
}

export function makeBlankBusinessArea(): BusinessAreaEntry {
  return {
    business_area_id: '',
    label: '',
    description: '',
  }
}

export function makeBlankNonGoal(): NonGoalEntry {
  return {
    statement: '',
    rationale: '',
  }
}

export function makeBlankSuccessCriteria(): SuccessCriteriaEntry {
  return {
    statement: '',
    evidence: '',
    priority: 'medium',
    review_method: '',
  }
}

export function defaultProductSummaryData(): ProductSummaryData {
  return {
    artifact_type: PRODUCT_SUMMARY_ARTIFACT_TYPE,
    product_purpose: '',
    business_problem: '',
    business_goals: [''],
    supported_question_families: [''],
    governed_behavior_summary: '',
    approval_posture_summary: '',
    multi_step_composition_rules: [''],
    why_now: '',
    success_outcome_summary: '',
  }
}

export function defaultActorModelData(): ActorModelData {
  return {
    artifact_type: ACTOR_MODEL_ARTIFACT_TYPE,
    actors: [makeBlankActor()],
  }
}

export function defaultBusinessAreasData(): BusinessAreasData {
  return {
    artifact_type: BUSINESS_AREAS_ARTIFACT_TYPE,
    entries: [makeBlankBusinessArea()],
  }
}

export function defaultPermissionIntentData(): PermissionIntentData {
  return {
    artifact_type: PERMISSION_INTENT_ARTIFACT_TYPE,
    policy_summary: '',
    rules: [makeBlankPermissionRule()],
  }
}

export function defaultNonGoalsData(): NonGoalsData {
  return {
    artifact_type: NON_GOALS_ARTIFACT_TYPE,
    entries: [makeBlankNonGoal()],
  }
}

export function defaultSuccessCriteriaData(): SuccessCriteriaData {
  return {
    artifact_type: SUCCESS_CRITERIA_ARTIFACT_TYPE,
    entries: [makeBlankSuccessCriteria()],
  }
}

export function productDesignArtifactId(projectId: string, type: ProductDesignArtifactType): string {
  return `${projectId}-${type}`
}

export function productDesignRevisionArtifactId(projectId: string, revisionNumber: number): string {
  return `${projectId}-product-design-revision-${revisionNumber}`
}

export function cloneProductDesignData<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

export function findProductDesignArtifact(
  artifacts: ArtifactRecord[],
  type: ProductDesignArtifactType,
): ArtifactRecord | null {
  return artifacts.find((artifact) => artifact.data?.artifact_type === type) ?? null
}

export function findProductSummaryArtifact(artifacts: ArtifactRecord[]): ArtifactRecord | null {
  return findProductDesignArtifact(artifacts, PRODUCT_SUMMARY_ARTIFACT_TYPE)
}

export function findProductDesignRevisionArtifacts(artifacts: ArtifactRecord[]): ArtifactRecord[] {
  return (artifacts ?? []).filter((artifact) => artifact.data?.artifact_type === PRODUCT_DESIGN_REVISION_ARTIFACT_TYPE)
}

export function findLatestProductDesignRevisionArtifact(artifacts: ArtifactRecord[]): ArtifactRecord | null {
  const revisions = [...findProductDesignRevisionArtifacts(artifacts)]
  revisions.sort((a, b) => {
    const aRevision = Number((a.data as ProductDesignRevisionData | undefined)?.revision_number ?? 0)
    const bRevision = Number((b.data as ProductDesignRevisionData | undefined)?.revision_number ?? 0)
    if (aRevision !== bRevision) return bRevision - aRevision
    return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  })
  return revisions[0] ?? null
}

export function productDesignSourceArtifacts(artifacts: ArtifactRecord[]): ArtifactRecord[] {
  const sourceTypes = new Set<ProductDesignArtifactType>([
    PRODUCT_SUMMARY_ARTIFACT_TYPE,
    ACTOR_MODEL_ARTIFACT_TYPE,
    BUSINESS_AREAS_ARTIFACT_TYPE,
    PERMISSION_INTENT_ARTIFACT_TYPE,
    NON_GOALS_ARTIFACT_TYPE,
    SUCCESS_CRITERIA_ARTIFACT_TYPE,
  ])
  return artifacts
    .filter((artifact) => sourceTypes.has(artifact.data?.artifact_type as ProductDesignArtifactType))
    .sort((a, b) => String(a.data?.artifact_type ?? '').localeCompare(String(b.data?.artifact_type ?? '')))
}

export function productDesignSourceHash(artifacts: ArtifactRecord[]): string | null {
  const parts = productDesignSourceArtifacts(artifacts).map((artifact) =>
    `${String(artifact.data?.artifact_type ?? '')}:${artifact.id}:${artifact.content_hash}`,
  )
  return parts.length > 0 ? parts.join('|') : null
}

export function buildProductDesignRevision(params: {
  projectId: string
  pmArtifacts: ArtifactRecord[]
  savedAt?: string
}): ProductDesignRevisionData {
  const latestRevision = findLatestProductDesignRevisionArtifact(params.pmArtifacts)?.data as ProductDesignRevisionData | undefined
  const revisionNumber = (latestRevision?.revision_number ?? 0) + 1
  const revisionArtifactId = productDesignRevisionArtifactId(params.projectId, revisionNumber)
  return {
    artifact_type: PRODUCT_DESIGN_REVISION_ARTIFACT_TYPE,
    revision_number: revisionNumber,
    revision_artifact_id: revisionArtifactId,
    previous_revision_artifact_id: latestRevision?.revision_artifact_id ?? null,
    product_design_hash: productDesignSourceHash(params.pmArtifacts),
    saved_at: params.savedAt ?? new Date().toISOString(),
    snapshot: productDesignSourceArtifacts(params.pmArtifacts).map((artifact) => ({
      artifact_type: artifact.data.artifact_type as ProductDesignArtifactType,
      artifact_id: artifact.id,
      title: artifact.title,
      content_hash: artifact.content_hash,
      updated_at: artifact.updated_at,
      data: cloneProductDesignData(artifact.data as ProductDesignArtifactData),
    })),
  }
}

export function findActorModelArtifact(artifacts: ArtifactRecord[]): ArtifactRecord | null {
  return findProductDesignArtifact(artifacts, ACTOR_MODEL_ARTIFACT_TYPE)
}

export function findPermissionIntentArtifact(artifacts: ArtifactRecord[]): ArtifactRecord | null {
  return findProductDesignArtifact(artifacts, PERMISSION_INTENT_ARTIFACT_TYPE)
}

export function findBusinessAreasArtifact(artifacts: ArtifactRecord[]): ArtifactRecord | null {
  return findProductDesignArtifact(artifacts, BUSINESS_AREAS_ARTIFACT_TYPE)
}

export function findNonGoalsArtifact(artifacts: ArtifactRecord[]): ArtifactRecord | null {
  return findProductDesignArtifact(artifacts, NON_GOALS_ARTIFACT_TYPE)
}

export function findSuccessCriteriaArtifact(artifacts: ArtifactRecord[]): ArtifactRecord | null {
  return findProductDesignArtifact(artifacts, SUCCESS_CRITERIA_ARTIFACT_TYPE)
}

function hasSavedSectionClarification(
  artifacts: ArtifactRecord[],
  mode: 'pm' | 'dev',
  sectionKey: string,
): boolean {
  return artifacts.some((artifact) => {
    const data = artifact.data ?? {}
    if (data.artifact_type !== ASSISTANT_SECTION_CLARIFICATIONS_ARTIFACT_TYPE) return false
    if (String(data.mode ?? '').trim() !== mode) return false
    if (String(data.section_key ?? '').trim() !== sectionKey) return false
    const payload = Array.isArray(data.accepted_payload) ? data.accepted_payload : []
    return payload.some((item) =>
      item && typeof item === 'object' && String((item as Record<string, unknown>).answer ?? '').trim().length > 0,
    )
  })
}

function textValue(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function textList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => textValue(item)).filter(Boolean) : []
}

function objectList<T>(value: unknown): T[] {
  return Array.isArray(value)
    ? value.filter((item): item is T => Boolean(item) && typeof item === 'object' && !Array.isArray(item))
    : []
}

export function isProductSummaryComplete(data: ProductSummaryData | null | undefined): boolean {
  if (!data) return false
  return (
    textValue(data.product_purpose).length > 0
    && textValue(data.business_problem).length > 0
    && textList(data.business_goals).length > 0
    && textList(data.supported_question_families).length > 0
    && textValue(data.governed_behavior_summary).length > 0
    && textValue(data.approval_posture_summary).length > 0
  )
}

export function isActorModelComplete(data: ActorModelData | null | undefined): boolean {
  if (!data) return false
  return objectList<ActorModelEntry>(data.actors).some((actor) =>
    textValue(actor.actor_id).length > 0
    && textValue(actor.title).length > 0
    && textValue(actor.summary).length > 0,
  )
}

export function isPermissionIntentComplete(data: PermissionIntentData | null | undefined): boolean {
  if (!data) return false
  return textValue(data.policy_summary).length > 0 && objectList<PermissionIntentRule>(data.rules).some((rule) =>
    !isStudioFallbackPermissionRule(rule)
    && textValue(rule.actor_id).length > 0
    && textValue(rule.business_area).length > 0
    && textValue(rule.access_posture).length > 0
    && textValue(rule.governed_outcome_type).length > 0
    && textValue(rule.governed_outcome).length > 0
  )
}

export function isStudioFallbackPermissionRule(rule: PermissionIntentRule | null | undefined): boolean {
  if (!rule) return false
  return textValue(rule.review_source) === PERMISSION_INTENT_FALLBACK_REVIEW_SOURCE
    || textValue(rule.notes).includes(PERMISSION_INTENT_FALLBACK_REVIEW_NOTE)
}

function concretePermissionRules(rules: PermissionIntentRule[] | undefined): PermissionIntentRule[] {
  return objectList<PermissionIntentRule>(rules).filter((rule) => !isStudioFallbackPermissionRule(rule))
}

export function isBusinessAreasComplete(data: BusinessAreasData | null | undefined): boolean {
  if (!data) return false
  return objectList<BusinessAreaEntry>(data.entries).some((entry) =>
    textValue(entry.business_area_id).length > 0
    && textValue(entry.label).length > 0,
  )
}

export function normalizeBusinessAreaId(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

export function resolveBusinessAreaLabel(
  businessAreaId: string,
  artifacts: ArtifactRecord[],
): string {
  const businessAreas = findBusinessAreasArtifact(artifacts)?.data as BusinessAreasData | undefined
  const normalizedBusinessAreaId = textValue(businessAreaId)
  const match = objectList<BusinessAreaEntry>(businessAreas?.entries).find((entry) => textValue(entry.business_area_id) === normalizedBusinessAreaId)
  return textValue(match?.label) || normalizedBusinessAreaId
}

export function isNonGoalsComplete(data: NonGoalsData | null | undefined): boolean {
  if (!data) return false
  return objectList<NonGoalEntry>(data.entries).some((entry) => textValue(entry.statement).length > 0)
}

export function isSuccessCriteriaComplete(data: SuccessCriteriaData | null | undefined): boolean {
  if (!data) return false
  return objectList<SuccessCriteriaEntry>(data.entries).some((entry) =>
    textValue(entry.statement).length > 0
    && textValue(entry.evidence).length > 0,
  )
}

export function buildProductDesignStatusCards(projectId: string, artifacts: ArtifactRecord[]): ProductDesignStatusCard[] {
  const summary = findProductSummaryArtifact(artifacts)?.data as ProductSummaryData | undefined
  const actors = findActorModelArtifact(artifacts)?.data as ActorModelData | undefined
  const businessAreas = findBusinessAreasArtifact(artifacts)?.data as BusinessAreasData | undefined
  const permissions = findPermissionIntentArtifact(artifacts)?.data as PermissionIntentData | undefined
  const nonGoals = findNonGoalsArtifact(artifacts)?.data as NonGoalsData | undefined
  const successCriteria = findSuccessCriteriaArtifact(artifacts)?.data as SuccessCriteriaData | undefined
  const concretePermissions = concretePermissionRules(permissions?.rules)
  const fallbackPermissionsCount = objectList<PermissionIntentRule>(permissions?.rules).filter((rule) => isStudioFallbackPermissionRule(rule)).length

  return [
    {
      key: PRODUCT_SUMMARY_ARTIFACT_TYPE,
      title: 'Business Summary',
      complete: isProductSummaryComplete(summary),
      detail: textValue(summary?.product_purpose) || 'Capture the product purpose, business problem, goals, and governed behavior.',
      path: `/design/projects/${projectId}/product-summary`,
    },
    {
      key: ACTOR_MODEL_ARTIFACT_TYPE,
      title: 'Actor Model',
      complete: isActorModelComplete(actors),
      detail: objectList<ActorModelEntry>(actors?.actors).filter((item) => textValue(item.title).length > 0).length
        ? `${objectList<ActorModelEntry>(actors?.actors).filter((item) => textValue(item.title).length > 0).length} actor entries recorded`
        : 'Define who uses the system and what each actor expects to see or do.',
      path: `/design/projects/${projectId}/actor-model`,
    },
    {
      key: BUSINESS_AREAS_ARTIFACT_TYPE,
      title: 'Business Areas',
      complete: isBusinessAreasComplete(businessAreas),
      detail: objectList<BusinessAreaEntry>(businessAreas?.entries).filter((item) =>
        textValue(item.business_area_id).length > 0
        && textValue(item.label).length > 0,
      ).length
        ? `${objectList<BusinessAreaEntry>(businessAreas?.entries).filter((item) =>
          textValue(item.business_area_id).length > 0
          && textValue(item.label).length > 0,
        ).length} business areas recorded`
        : 'Define the stable business-area ids that Permission Intent and downstream formalization should reuse.',
      path: `/design/projects/${projectId}/business-areas`,
    },
    {
      key: PERMISSION_INTENT_ARTIFACT_TYPE,
      title: 'Permission Intent',
      complete: isPermissionIntentComplete(permissions),
      detail: fallbackPermissionsCount
        ? `${fallbackPermissionsCount} derived placeholder permission rules need concrete PM review`
        : concretePermissions.filter((item) =>
        textValue(item.business_area).length > 0
        && textValue(item.governed_outcome_type).length > 0,
      ).length
        ? `${concretePermissions.filter((item) =>
          textValue(item.business_area).length > 0
          && textValue(item.governed_outcome_type).length > 0,
        ).length} permission rules with outcome classes recorded`
        : 'Capture actor-by-business-area access posture and the governed outcome class the product should produce.',
      path: `/design/projects/${projectId}/permission-intent`,
    },
    {
      key: NON_GOALS_ARTIFACT_TYPE,
      title: 'Non-Goals',
      complete: isNonGoalsComplete(nonGoals),
      detail: objectList<NonGoalEntry>(nonGoals?.entries).filter((item) => textValue(item.statement).length > 0).length
        ? `${objectList<NonGoalEntry>(nonGoals?.entries).filter((item) => textValue(item.statement).length > 0).length} non-goals recorded`
        : 'State what the product intentionally does not do.',
      path: `/design/projects/${projectId}/non-goals`,
    },
    {
      key: SUCCESS_CRITERIA_ARTIFACT_TYPE,
      title: 'Success Criteria',
      complete: isSuccessCriteriaComplete(successCriteria),
      detail: objectList<SuccessCriteriaEntry>(successCriteria?.entries).filter((item) => textValue(item.statement).length > 0).length
        ? `${objectList<SuccessCriteriaEntry>(successCriteria?.entries).filter((item) => textValue(item.statement).length > 0).length} success criteria recorded`
        : 'Define how PM and business stakeholders will know the product is working.',
      path: `/design/projects/${projectId}/success-criteria`,
    },
  ]
}

function hasSourceSignal(context: ProductDesignSufficiencyContext): boolean {
  return context.documents_count > 0 || context.requirements_count > 0 || context.scenarios_count > 0
}

function hasDraftContent(values: Array<string | undefined | null>): boolean {
  return values.some((value) => (value ?? '').trim().length > 0)
}

function sufficiencyActionLabel(status: DesignSectionSufficiencyStatus): string {
  switch (status) {
    case 'ready':
      return 'Review'
    case 'draftable':
      return 'Draft From Source'
    case 'needs_clarification':
      return 'Resolve Gaps'
    default:
      return 'Unblock'
  }
}

export function buildProductDesignSufficiencyCards(
  projectId: string,
  artifacts: ArtifactRecord[],
  context: ProductDesignSufficiencyContext,
): DesignSectionSufficiencyCard[] {
  const summary = findProductSummaryArtifact(artifacts)?.data as ProductSummaryData | undefined
  const actors = findActorModelArtifact(artifacts)?.data as ActorModelData | undefined
  const businessAreas = findBusinessAreasArtifact(artifacts)?.data as BusinessAreasData | undefined
  const permissions = findPermissionIntentArtifact(artifacts)?.data as PermissionIntentData | undefined
  const nonGoals = findNonGoalsArtifact(artifacts)?.data as NonGoalsData | undefined
  const successCriteria = findSuccessCriteriaArtifact(artifacts)?.data as SuccessCriteriaData | undefined
  const concretePermissions = concretePermissionRules(permissions?.rules)
  const fallbackPermissionsCount = objectList<PermissionIntentRule>(permissions?.rules).filter((rule) => isStudioFallbackPermissionRule(rule)).length

  const sourceSignal = hasSourceSignal(context)
  const actorModelReady = isActorModelComplete(actors)
  const businessAreasReady = isBusinessAreasComplete(businessAreas)

  const summaryQuestions = [
    !textValue(summary?.product_purpose) ? 'What is the product trying to accomplish?' : null,
    !textValue(summary?.business_problem) ? 'What business problem is it solving?' : null,
    textList(summary?.business_goals).length === 0 ? 'Which business goals must Studio preserve?' : null,
    textList(summary?.supported_question_families).length === 0 ? 'Which user question families should this product answer?' : null,
    !textValue(summary?.governed_behavior_summary) ? 'What governed behavior should the product preserve by default?' : null,
    !textValue(summary?.approval_posture_summary) ? 'When should the product stop for approval instead of acting directly?' : null,
  ].filter((item): item is string => Boolean(item))

  const actorQuestions = [
    !objectList<ActorModelEntry>(actors?.actors).some((actor) => textValue(actor.actor_id).length > 0) ? 'Which distinct actors need separate treatment?' : null,
    !objectList<ActorModelEntry>(actors?.actors).some((actor) => textValue(actor.title).length > 0) ? 'What titles should PM and Dev use for those actors?' : null,
    !objectList<ActorModelEntry>(actors?.actors).some((actor) => textValue(actor.summary).length > 0) ? 'What does each actor actually want to see or do?' : null,
  ].filter((item): item is string => Boolean(item))

  const businessAreaQuestions = [
    !objectList<BusinessAreaEntry>(businessAreas?.entries).some((entry) => textValue(entry.business_area_id).length > 0) ? 'Which stable business-area ids should downstream policy reuse?' : null,
    !objectList<BusinessAreaEntry>(businessAreas?.entries).some((entry) => textValue(entry.label).length > 0) ? 'What user-facing labels should those business areas carry?' : null,
  ].filter((item): item is string => Boolean(item))

  const permissionQuestions = [
    !actorModelReady ? 'Finish the Actor Model first so access posture can bind to real actors.' : null,
    !businessAreasReady ? 'Finish Business Areas first so permission rules bind to stable scopes.' : null,
    !textValue(permissions?.policy_summary) ? 'What trust and access posture should the product communicate overall?' : null,
    fallbackPermissionsCount ? 'Replace derived placeholder permission rules with concrete reviewed actor-by-business-area rules.' : null,
    !concretePermissions.some((rule) => textValue(rule.actor_id).length > 0 && textValue(rule.business_area).length > 0) ? 'Which actor-by-business-area combinations need explicit rules?' : null,
    !concretePermissions.some((rule) => textValue(rule.governed_outcome_type).length > 0 && textValue(rule.governed_outcome).length > 0) ? 'Should the system allow, restrict, deny, clarify, or stop for approval in each case?' : null,
  ].filter((item): item is string => Boolean(item))

  const nonGoalQuestions = [
    !objectList<NonGoalEntry>(nonGoals?.entries).some((entry) => textValue(entry.statement).length > 0) ? 'What should the product explicitly not do?' : null,
    !objectList<NonGoalEntry>(nonGoals?.entries).some((entry) => textValue(entry.rationale).length > 0) ? 'Why are those exclusions important?' : null,
  ].filter((item): item is string => Boolean(item))

  const successQuestions = [
    !objectList<SuccessCriteriaEntry>(successCriteria?.entries).some((entry) => textValue(entry.statement).length > 0) ? 'What business outcomes will prove this product is working?' : null,
    !objectList<SuccessCriteriaEntry>(successCriteria?.entries).some((entry) => textValue(entry.evidence).length > 0) ? 'What evidence should PM review to confirm success?' : null,
  ].filter((item): item is string => Boolean(item))

  const cards: Array<{
    key: ProductDesignArtifactType
    title: string
    path: string
    ready: boolean
    hasDraft: boolean
    draftable: boolean
    detail: string
    questions: string[]
  }> = [
    {
      key: PRODUCT_SUMMARY_ARTIFACT_TYPE,
      title: 'Business Summary',
      path: `/design/projects/${projectId}/product-summary`,
      ready: isProductSummaryComplete(summary),
      hasDraft: hasDraftContent([
        textValue(summary?.product_purpose),
        textValue(summary?.business_problem),
        textValue(summary?.governed_behavior_summary),
        textValue(summary?.approval_posture_summary),
      ]),
      draftable: sourceSignal,
      detail: textValue(summary?.product_purpose) || 'Use the source brief to draft the product purpose, problem statement, goals, and governed behavior.',
      questions: summaryQuestions,
    },
    {
      key: ACTOR_MODEL_ARTIFACT_TYPE,
      title: 'Actor Model',
      path: `/design/projects/${projectId}/actor-model`,
      ready: actorModelReady,
      hasDraft: objectList<ActorModelEntry>(actors?.actors).some((actor) => hasDraftContent([actor.actor_id, actor.title, actor.summary])),
      draftable: sourceSignal || isProductSummaryComplete(summary),
      detail: objectList<ActorModelEntry>(actors?.actors).filter((item) => textValue(item.title).length > 0).length
        ? `${objectList<ActorModelEntry>(actors?.actors).filter((item) => textValue(item.title).length > 0).length} actor entries started`
        : 'Use the business spec and scenarios to draft the actor surface before asking for approvals or visibility details.',
      questions: actorQuestions,
    },
    {
      key: BUSINESS_AREAS_ARTIFACT_TYPE,
      title: 'Business Areas',
      path: `/design/projects/${projectId}/business-areas`,
      ready: businessAreasReady,
      hasDraft: objectList<BusinessAreaEntry>(businessAreas?.entries).some((entry) => hasDraftContent([entry.business_area_id, entry.label, entry.description])),
      draftable: sourceSignal || context.requirements_count > 0 || context.scenarios_count > 0,
      detail: objectList<BusinessAreaEntry>(businessAreas?.entries).filter((entry) => textValue(entry.label).length > 0).length
        ? `${objectList<BusinessAreaEntry>(businessAreas?.entries).filter((entry) => textValue(entry.label).length > 0).length} business areas started`
        : 'Reuse the source brief, requirements, and scenarios to draft the stable business areas the product should preserve.',
      questions: businessAreaQuestions,
    },
    {
      key: PERMISSION_INTENT_ARTIFACT_TYPE,
      title: 'Permission Intent',
      path: `/design/projects/${projectId}/permission-intent`,
      ready: isPermissionIntentComplete(permissions),
      hasDraft: hasDraftContent([textValue(permissions?.policy_summary)]) || objectList<PermissionIntentRule>(permissions?.rules).some((rule) =>
        hasDraftContent([rule.actor_id, rule.business_area, rule.governed_outcome_type, rule.governed_outcome]),
      ),
      draftable: actorModelReady && businessAreasReady,
      detail: textValue(permissions?.policy_summary)
        || 'Draft PM-owned trust posture after Actor Model and Business Areas are in place; only ask for outcome classes that the brief does not make clear.',
      questions: permissionQuestions,
    },
    {
      key: NON_GOALS_ARTIFACT_TYPE,
      title: 'Non-Goals',
      path: `/design/projects/${projectId}/non-goals`,
      ready: isNonGoalsComplete(nonGoals),
      hasDraft: objectList<NonGoalEntry>(nonGoals?.entries).some((entry) => hasDraftContent([entry.statement, entry.rationale])),
      draftable: sourceSignal || context.requirements_count > 0,
      detail: textValue(objectList<NonGoalEntry>(nonGoals?.entries).find((entry) => textValue(entry.statement).length > 0)?.statement)
        || 'Draft explicit exclusions from the source brief and only ask where the product boundaries remain ambiguous.',
      questions: nonGoalQuestions,
    },
    {
      key: SUCCESS_CRITERIA_ARTIFACT_TYPE,
      title: 'Success Criteria',
      path: `/design/projects/${projectId}/success-criteria`,
      ready: isSuccessCriteriaComplete(successCriteria),
      hasDraft: objectList<SuccessCriteriaEntry>(successCriteria?.entries).some((entry) => hasDraftContent([entry.statement, entry.evidence, entry.review_method])),
      draftable: sourceSignal || isProductSummaryComplete(summary),
      detail: textValue(objectList<SuccessCriteriaEntry>(successCriteria?.entries).find((entry) => textValue(entry.statement).length > 0)?.statement)
        || 'Draft stakeholder-visible success checks from the brief and ask only for the evidence that is still missing.',
      questions: successQuestions,
    },
  ]

  return cards.map((card) => {
    const clarificationResolved = hasSavedSectionClarification(artifacts, 'pm', card.key)
    let status: DesignSectionSufficiencyStatus
    if (card.ready) {
      status = 'ready'
    } else if (clarificationResolved) {
      status = 'draftable'
    } else if (card.hasDraft) {
      status = 'needs_clarification'
    } else if (card.draftable) {
      status = 'draftable'
    } else {
      status = 'blocked'
    }

    return {
      key: card.key,
      title: card.title,
      status,
      detail: clarificationResolved
        ? `${card.title} has saved clarification answers. Rerun the draft step to fold them into the canonical artifact.`
        : card.detail,
      path: card.path,
      action_label: sufficiencyActionLabel(status),
      questions: (clarificationResolved ? [] : card.questions).slice(0, 3),
    }
  })
}
