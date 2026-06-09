export type ProjectConsumerMode = 'agent_anip' | 'hybrid'

export const DEFAULT_CONSUMER_MODE: ProjectConsumerMode = 'hybrid'

export const CONSUMER_LABEL_PREFIX = 'consumer:'

const CONSUMER_MODE_LABELS: Record<ProjectConsumerMode, string> = {
  hybrid: 'Both people and agents',
  agent_anip: 'Agents/tools through ANIP',
}

export const CONSUMER_MODE_OPTIONS: Array<{
  value: ProjectConsumerMode
  label: string
  description: string
}> = [
  {
    value: 'hybrid',
    label: CONSUMER_MODE_LABELS.hybrid,
    description: 'Design both the human product workflow and the governed ANIP capability surface.',
  },
  {
    value: 'agent_anip',
    label: CONSUMER_MODE_LABELS.agent_anip,
    description: 'Optimize the design for direct agent/tool consumption through explicit ANIP capabilities.',
  },
]

export function consumerModeTag(mode: ProjectConsumerMode): string {
  return `${CONSUMER_LABEL_PREFIX}${mode}`
}

export function labelsWithConsumerMode(labels: string[] | undefined, mode: ProjectConsumerMode): string[] {
  const preserved = (labels ?? []).filter(label => !label.startsWith(CONSUMER_LABEL_PREFIX))
  return [...preserved, consumerModeTag(mode)]
}

export function consumerModeFromLabels(labels: string[] | undefined): ProjectConsumerMode {
  const match = (labels ?? []).find(label => label.startsWith(CONSUMER_LABEL_PREFIX))
  const value = match?.slice(CONSUMER_LABEL_PREFIX.length)
  if (value === 'agent_anip' || value === 'hybrid') return value
  return DEFAULT_CONSUMER_MODE
}

export function consumerModeLabel(mode: ProjectConsumerMode): string {
  return CONSUMER_MODE_LABELS[mode] ?? CONSUMER_MODE_LABELS[DEFAULT_CONSUMER_MODE]
}
