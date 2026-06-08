import type {
  DataAccessBackendType,
  DataAccessClarificationConfig,
  DataAccessGeneratedOutput,
  DataAccessGovernedOutcome,
  DataAccessImplementationLanguage,
  DataAccessProjectState,
} from './types'

export const DATA_ACCESS_BACKEND_OPTIONS: Array<{ value: DataAccessBackendType; label: string; description: string }> = [
  {
    value: 'internal_metrics_api',
    label: 'Internal Metrics API',
    description: 'Front an existing governed metrics or analytics API.',
  },
  {
    value: 'cube_rest',
    label: 'Cube',
    description: 'Map bounded ANIP intent into Cube query payloads.',
  },
  {
    value: 'snowflake_sql',
    label: 'Snowflake SQL',
    description: 'Map bounded ANIP intent into governed Snowflake warehouse execution requests.',
  },
  {
    value: 'snowflake_semantic',
    label: 'Snowflake Semantic',
    description: 'Map bounded ANIP intent into Snowflake semantic views / Cortex-style governed analytics requests.',
  },
  {
    value: 'databricks_sql',
    label: 'Databricks SQL',
    description: 'Map bounded ANIP intent into Databricks SQL warehouse requests.',
  },
  {
    value: 'databricks_genie',
    label: 'Databricks Genie',
    description: 'Map bounded ANIP intent into Databricks semantic or conversational analytics runtimes.',
  },
  {
    value: 'dbt_semantic',
    label: 'dbt Semantic Layer',
    description: 'Map bounded ANIP intent into semantic query requests.',
  },
  {
    value: 'curated_sql',
    label: 'Curated SQL Planner',
    description: 'Use a provider-owned SQL planning layer behind ANIP.',
  },
  {
    value: 'custom_adapter',
    label: 'Custom Adapter',
    description: 'Generate a skeleton for a custom system-of-truth adapter.',
  },
]

export const DATA_ACCESS_IMPLEMENTATION_LANGUAGE_OPTIONS: Array<{ value: DataAccessImplementationLanguage; label: string; description: string }> = [
  {
    value: 'typescript',
    label: 'TypeScript',
    description: 'Generate TypeScript-first ANIP service and adapter starter files.',
  },
  {
    value: 'python',
    label: 'Python',
    description: 'Generate Python-first ANIP service and adapter starter files.',
  },
]

export const DEFAULT_GOVERNED_OUTCOMES: Record<DataAccessGovernedOutcome, boolean> = {
  available: true,
  restricted: true,
  denied: true,
  clarification_required: true,
}

export const DEFAULT_CLARIFICATION_RULES: DataAccessClarificationConfig = {
  rules: [
    { key: 'ambiguous_ranking_metric', enabled: true },
    { key: 'ambiguous_time_semantics', enabled: true },
    { key: 'ambiguous_entity_grain', enabled: false },
    { key: 'ambiguous_account_hierarchy', enabled: false },
  ],
}

function defaultTargetLabel(type: DataAccessBackendType): string {
  switch (type) {
    case 'cube_rest':
      return 'Cube semantic query surface'
    case 'snowflake_sql':
      return 'Snowflake governed query surface'
    case 'snowflake_semantic':
      return 'Snowflake semantic analytics surface'
    case 'databricks_sql':
      return 'Databricks SQL warehouse'
    case 'databricks_genie':
      return 'Databricks Genie analytics surface'
    case 'dbt_semantic':
      return 'dbt semantic query surface'
    case 'curated_sql':
      return 'Curated SQL planner'
    case 'custom_adapter':
      return 'Custom governed data backend'
    case 'internal_metrics_api':
    default:
      return 'Governed metrics API'
  }
}

export function createDraftDataAccessProjectState(
  name: string,
  description = '',
  backendType: DataAccessBackendType = 'internal_metrics_api',
  implementationLanguage: DataAccessImplementationLanguage = 'typescript',
): DataAccessProjectState {
  return {
    kind: 'governed_data_access',
    version: 1,
    name,
    description,
    backend: {
      type: backendType,
      targetLabel: defaultTargetLabel(backendType),
      adapterMode: 'generated_scaffold',
      implementationLanguage,
    },
    domain: {
      name: 'sales_analytics',
      metrics: [{ key: 'sales_amount', label: 'Sales Amount' }],
      dimensions: [{ key: 'customer', label: 'Customer' }],
      filters: [{ key: 'time_window', label: 'Time Window' }],
      grains: ['aggregate'],
      resultModes: ['exploratory', 'decision_grade'],
    },
    governedOutcomes: { ...DEFAULT_GOVERNED_OUTCOMES },
    permissions: {
      metricRules: [],
      dimensionRules: [],
      limitRules: [],
      useRules: [],
    },
    clarification: {
      rules: DEFAULT_CLARIFICATION_RULES.rules.map(rule => ({ ...rule })),
    },
    scenarioPack: {
      categories: ['allowed', 'restricted', 'denied', 'clarification_required'],
      targetCount: 12,
    },
  }
}

export function emptyGeneratedOutput(
  kind: DataAccessGeneratedOutput['kind'],
  title: string,
  filename: string,
  contentType: DataAccessGeneratedOutput['contentType'],
): DataAccessGeneratedOutput {
  return {
    kind,
    title,
    filename,
    contentType,
    content: '',
    generatedAt: new Date(0).toISOString(),
  }
}
