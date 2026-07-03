import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

describe('desktop boot shell', () => {
  it('renders a static startup shell before Vue mounts', () => {
    const html = readFileSync(resolve(__dirname, '../../index.html'), 'utf-8')

    expect(html).toContain('class="studio-boot-shell"')
    expect(html).toContain('Starting local workspace')
    expect(html).toContain('Loading the desktop shell and preparing the local Studio API.')
  })
})
