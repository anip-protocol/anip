/** Answer types supported by guided questions */
export type AnswerType = 'boolean' | 'select' | 'text'

/** A single option for select-type answers */
export interface SelectOption {
  value: string
  label: string
  description?: string
}

/** Maps a guided answer to one or more artifact fields */
export interface FieldMapping {
  /** Dot-separated path into the requirements artifact (e.g. "audit.durable") */
  path: string
  /** Human-readable label for the mapped field */
  label: string
}

/** A single guided question */
export interface GuidedQuestion {
  id: string
  prompt: string
  helpText?: string
  inlineDetails?: string[]
  helpDialog?: {
    title?: string
    summary?: string
    bullets?: string[]
    example?: string
    decisionOwner?: string
  }
  answerType: AnswerType
  /** Render text answers as a multiline field when the content is narrative */
  multiline?: boolean
  /** Maximum character length for text answers */
  maxLength?: number
  /** For select answers */
  options?: SelectOption[]
  /** Which artifact fields this question maps to */
  fieldMappings: FieldMapping[]
  /** Default answer value when starting fresh */
  defaultValue: any
}

/** A section grouping related questions */
export interface GuidedSection {
  id: string
  title: string
  description: string
  inlineDetails?: string[]
  helpDialog?: {
    title?: string
    summary?: string
    bullets?: string[]
    example?: string
    decisionOwner?: string
  }
  questions: GuidedQuestion[]
}

/** An advisory completeness/ambiguity hint */
export interface CompletenessHint {
  id: string
  severity: 'info' | 'warning'
  message: string
  explanation: string
  /** Which artifact fields are relevant to this hint */
  relatedFields: string[]
}
