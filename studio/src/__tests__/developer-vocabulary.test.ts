import { describe, expect, it } from 'vitest'

import {
  developerLabel,
  developerLabelWithTechnical,
  developerTechnicalLabel,
  developerVocabularyEntry,
  formatDeveloperList,
  optionLabel,
} from '../design/developer-vocabulary'

describe('developer vocabulary', () => {
  it('renders common developer enum values as human-readable labels', () => {
    expect(developerLabel('composed')).toBe('Composed capability')
    expect(developerLabel('approval_required')).toBe('Approval required')
    expect(developerLabel('raw_data_export')).toBe('Export raw data')
    expect(developerLabel('masked_or_restricted_result')).toBe('Masked or restricted result')
    expect(developerLabel('multi_service_estate')).toBe('Multiple service boundaries')
    expect(developerLabel('multiple_coordinated_services')).toBe('Multiple coordinated services')
    expect(developerLabel('service_owned')).toBe('Owned by this service')
    expect(developerLabel('approval_required_for_high_risk')).toBe('Approval required for high-risk work')
    expect(developerLabel('service_metadata_insufficient')).toBe('Service metadata is insufficient')
    expect(developerLabel('capability_identity')).toBe('Capability identity')
    expect(developerLabel('developer_design')).toBe('Developer design')
    expect(developerLabel('unsupported_effect')).toBe('Unsupported effect')
  })

  it('keeps canonical identifiers available as secondary detail', () => {
    expect(developerTechnicalLabel('multi_service_estate')).toBe('Canonical value: multi_service_estate')
    expect(developerLabelWithTechnical('multi_service_estate')).toBe('Multiple service boundaries (multi_service_estate)')
  })

  it('formats lists without exposing raw protocol identifiers', () => {
    expect(formatDeveloperList(['anip_http', 'async_events'])).toBe('ANIP over HTTP, Async events')
  })

  it('uses explicit option labels when supplied', () => {
    expect(optionLabel([{ value: 'from_service_design', label: 'Generate From Service Design' }], 'from_service_design')).toBe('Generate From Service Design')
  })

  it('falls back safely for unknown values', () => {
    expect(developerVocabularyEntry('partner.custom_mode').label).toBe('Partner Custom Mode')
  })
})
