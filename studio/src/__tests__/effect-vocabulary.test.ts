import { describe, expect, it } from 'vitest'

import {
  describeEffect,
  effectLabel,
  formatEffectList,
  formatEffectListWithTechnical,
  groupedEffectDescriptions,
  technicalEffectDetails,
  technicalEffectLabel,
} from '../design/effect-vocabulary'

describe('effect vocabulary', () => {
  it('renders canonical effect identifiers as human-readable labels', () => {
    expect(effectLabel('content.draft')).toBe('Draft content')
    expect(effectLabel('approval.request')).toBe('Ask for approval')
    expect(effectLabel('raw_data_export')).toBe('Export raw data')
  })

  it('keeps technical identifiers available for canonical payloads', () => {
    expect(formatEffectList(['approval.request', 'system.preview_mutation'])).toBe('Ask for approval, Preview a change')
    expect(technicalEffectDetails(['approval.request', 'system.preview_mutation'])).toBe('approval.request, system.preview_mutation')
    expect(technicalEffectLabel(['approval.request'])).toBe('Canonical values: approval.request')
    expect(formatEffectListWithTechnical(['approval.request'])).toBe('Ask for approval (approval.request)')
  })

  it('groups effects by human-readable categories', () => {
    const groups = groupedEffectDescriptions(['content.summary', 'raw_data_export'])

    expect(groups.map((group) => group.categoryLabel)).toEqual(['Content', 'Restricted data'])
  })

  it('falls back safely for unknown effect identifiers', () => {
    const description = describeEffect('partner.custom_effect')

    expect(description.label).toBe('Partner Custom Effect')
    expect(description.categoryLabel).toBe('Other')
    expect(description.posture).toBe('unknown')
  })
})
