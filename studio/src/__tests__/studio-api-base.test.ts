import { describe, expect, it } from 'vitest'

import { resolveStudioApiUrl, studioApiUrl } from '../design/api-base'
import { configureStudioApiBase } from '../design/desktop-mode'

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

  it('uses a runtime-configured desktop API base', () => {
    configureStudioApiBase('http://127.0.0.1:49152/')

    expect(studioApiUrl('/api/readyz')).toBe('http://127.0.0.1:49152/api/readyz')

    configureStudioApiBase('')
  })
})
