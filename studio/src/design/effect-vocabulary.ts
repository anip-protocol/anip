export type EffectCategory = 'content' | 'data' | 'restricted_data' | 'system_action' | 'external_action' | 'approval' | 'other'
export type EffectPosture = 'safe' | 'governed' | 'restricted' | 'unknown'

export interface EffectVocabularyEntry {
  id: string
  label: string
  category: EffectCategory
  categoryLabel: string
  posture: EffectPosture
  description: string
}

const effectVocabulary: Record<string, EffectVocabularyEntry> = {
  'content.draft': {
    id: 'content.draft',
    label: 'Draft content',
    category: 'content',
    categoryLabel: 'Content',
    posture: 'safe',
    description: 'Produces editable draft material.',
  },
  'content.summary': {
    id: 'content.summary',
    label: 'Summarize information',
    category: 'content',
    categoryLabel: 'Content',
    posture: 'safe',
    description: 'Produces a bounded explanation or summary.',
  },
  'content.recommendation': {
    id: 'content.recommendation',
    label: 'Recommend options',
    category: 'content',
    categoryLabel: 'Content',
    posture: 'safe',
    description: 'Produces ranked or suggested options.',
  },
  'data.read': {
    id: 'data.read',
    label: 'Read bounded data',
    category: 'data',
    categoryLabel: 'Data',
    posture: 'safe',
    description: 'Reads data within the declared scope.',
  },
  'data.aggregate': {
    id: 'data.aggregate',
    label: 'Aggregate data',
    category: 'data',
    categoryLabel: 'Data',
    posture: 'safe',
    description: 'Computes grouped or summarized data.',
  },
  'data.export': {
    id: 'data.export',
    label: 'Export data',
    category: 'data',
    categoryLabel: 'Data',
    posture: 'governed',
    description: 'Produces a data export.',
  },
  raw_data_export: {
    id: 'raw_data_export',
    label: 'Export raw data',
    category: 'restricted_data',
    categoryLabel: 'Restricted data',
    posture: 'restricted',
    description: 'Exposes raw or underlying records.',
  },
  raw_model_features: {
    id: 'raw_model_features',
    label: 'Expose raw model features',
    category: 'restricted_data',
    categoryLabel: 'Restricted data',
    posture: 'restricted',
    description: 'Exposes raw model inputs, features, scoring internals, or feature-level evidence.',
  },
  'system.preview_mutation': {
    id: 'system.preview_mutation',
    label: 'Preview a change',
    category: 'system_action',
    categoryLabel: 'System action',
    posture: 'governed',
    description: 'Previews a system change without executing it.',
  },
  'system.mutation': {
    id: 'system.mutation',
    label: 'Change system state',
    category: 'system_action',
    categoryLabel: 'System action',
    posture: 'restricted',
    description: 'Changes state in an internal system.',
  },
  external_dispatch: {
    id: 'external_dispatch',
    label: 'Send outside the system',
    category: 'external_action',
    categoryLabel: 'External action',
    posture: 'restricted',
    description: 'Sends, publishes, dispatches, or contacts externally.',
  },
  'approval.request': {
    id: 'approval.request',
    label: 'Ask for approval',
    category: 'approval',
    categoryLabel: 'Approval',
    posture: 'governed',
    description: 'Creates or requires an approval request.',
  },
  'approval.execute': {
    id: 'approval.execute',
    label: 'Execute approved action',
    category: 'approval',
    categoryLabel: 'Approval',
    posture: 'restricted',
    description: 'Executes the governed action after approval.',
  },
}

export const KNOWN_EFFECT_IDS = Object.freeze(Object.keys(effectVocabulary))

export function isKnownEffect(effectId: string): boolean {
  return Object.prototype.hasOwnProperty.call(effectVocabulary, String(effectId || '').trim())
}

export function describeEffect(effectId: string): EffectVocabularyEntry {
  const id = String(effectId || '').trim()
  return effectVocabulary[id] ?? {
    id,
    label: id ? id.replace(/[._-]+/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase()) : 'Unknown effect',
    category: 'other',
    categoryLabel: 'Other',
    posture: 'unknown',
    description: id ? 'No human-readable description is registered for this effect yet.' : 'No effect was provided.',
  }
}

export function effectLabel(effectId: string): string {
  return describeEffect(effectId).label
}

export function formatEffectList(effectIds: string[] | undefined | null): string {
  const values = (effectIds ?? []).filter((value) => String(value || '').trim())
  return values.length ? values.map((value) => effectLabel(value)).join(', ') : 'None'
}

export function groupedEffectDescriptions(effectIds: string[] | undefined | null): Array<{
  category: EffectCategory
  categoryLabel: string
  effects: EffectVocabularyEntry[]
}> {
  const groups = new Map<EffectCategory, { category: EffectCategory; categoryLabel: string; effects: EffectVocabularyEntry[] }>()
  for (const id of effectIds ?? []) {
    const entry = describeEffect(id)
    const existing = groups.get(entry.category)
    if (existing) existing.effects.push(entry)
    else groups.set(entry.category, { category: entry.category, categoryLabel: entry.categoryLabel, effects: [entry] })
  }
  return Array.from(groups.values())
}

export function technicalEffectDetails(effectIds: string[] | undefined | null): string {
  const values = (effectIds ?? []).filter((value) => String(value || '').trim())
  return values.length ? values.join(', ') : 'No canonical effect IDs'
}

export function technicalEffectLabel(effectIds: string[] | undefined | null): string {
  return `Canonical values: ${technicalEffectDetails(effectIds)}`
}

export function formatEffectListWithTechnical(effectIds: string[] | undefined | null): string {
  const human = formatEffectList(effectIds)
  const technical = technicalEffectDetails(effectIds)
  return technical === 'No canonical effect IDs' ? human : `${human} (${technical})`
}
