import { describe, expect, it } from 'vitest'

import { resolveStudioApiUrl } from '../design/api-base'

describe('studio API URL resolver', () => {
  it('keeps relative API paths when no Studio API base is configured', () => {
    expect(resolveStudioApiUrl('/api/health', '')).toBe('/api/health')
  })

  it('targets the configured local Studio API base in desktop builds', () => {
    expect(resolveStudioApiUrl('/api/health', 'http://127.0.0.1:8100/')).toBe(
      'http://127.0.0.1:8100/api/health',
    )
  })

  it('does not rewrite absolute external URLs', () => {
    expect(resolveStudioApiUrl('https://service.example/anip/discovery', 'http://127.0.0.1:8100')).toBe(
      'https://service.example/anip/discovery',
    )
  })
})
