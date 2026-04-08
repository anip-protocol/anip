export type ProjectConsumerMode = 'human_app' | 'agent_anip' | 'hybrid'

export const DEFAULT_CONSUMER_MODE: ProjectConsumerMode = 'hybrid'

export const CONSUMER_LABEL_PREFIX = 'consumer:'

export const CONSUMER_MODE_OPTIONS: Array<{
  value: ProjectConsumerMode
  label: string
  description: string
}> = [
  {
    value: 'hybrid',
    label: 'Both people and agents',
    description: 'Recommended when a human workflow and an ANIP surface both matter.',
  },
  {
    value: 'human_app',
    label: 'People through an app',
    description: 'Bias the design toward operator flow, explainability, and product simplicity.',
  },
  {
    value: 'agent_anip',
    label: 'Agents/tools through ANIP',
    description: 'Bias the design toward machine-usable capabilities and low-glue protocol consumption.',
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
  if (value === 'human_app' || value === 'agent_anip' || value === 'hybrid') return value
  return DEFAULT_CONSUMER_MODE
}

export function consumerModeLabel(mode: ProjectConsumerMode): string {
  return CONSUMER_MODE_OPTIONS.find(option => option.value === mode)?.label ?? CONSUMER_MODE_OPTIONS[0].label
}
