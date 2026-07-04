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

  it('uses a native splash window while the main desktop window starts', () => {
    const config = JSON.parse(
      readFileSync(resolve(__dirname, '../../src-tauri/tauri.conf.json'), 'utf-8'),
    )
    const windows = Object.fromEntries(
      config.app.windows.map((window: { label: string }) => [window.label, window]),
    )

    expect(windows.main).toMatchObject({
      visible: false,
      backgroundColor: '#f6efe1',
    })
    expect(windows.splashscreen).toMatchObject({
      title: 'ANIP Studio',
      visible: true,
      decorations: false,
      resizable: false,
      skipTaskbar: true,
      backgroundColor: '#f6efe1',
    })
  })

  it('renders the desktop splash as a static image asset', () => {
    const html = readFileSync(resolve(__dirname, '../../public/splashscreen.html'), 'utf-8')
    const svg = readFileSync(resolve(__dirname, '../../public/splashscreen.svg'), 'utf-8')

    expect(html).toContain('src="./splashscreen.svg"')
    expect(html).toContain('background: #f6efe1')
    expect(svg).toContain('Starting ANIP Studio')
    expect(svg).toContain('Preparing local workspace and embedded API')
  })
})
