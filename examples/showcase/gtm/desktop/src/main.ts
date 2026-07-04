import { invoke } from '@tauri-apps/api/core'

const app = document.querySelector<HTMLDivElement>('#app')

function render(message: string, detail = '') {
  if (!app) return
  app.innerHTML = `
    <section style="font-family: Avenir Next, Segoe UI, sans-serif; display: grid; place-items: center; min-height: 100vh; color: #f4efe5; background: radial-gradient(circle at 20% 10%, #263845, #101820 48%, #090d12);">
      <div style="width: min(720px, calc(100vw - 48px)); border: 1px solid rgba(244,239,229,.16); border-radius: 28px; background: rgba(16,24,32,.86); box-shadow: 0 28px 90px rgba(0,0,0,.42); padding: 34px;">
        <p style="color: #f29d38; text-transform: uppercase; letter-spacing: .12em; font-size: 12px; font-weight: 800; margin: 0 0 10px;">ANIP Showcase</p>
        <h1 style="font-size: 42px; margin: 0 0 12px;">GTM Agent Desktop</h1>
        <p style="max-width: 620px; line-height: 1.6; color: #c8d1da; margin: 0;">${message}</p>
        ${detail ? `<p style="color: #8292a2; font-size: 13px; margin: 18px 0 0;">${detail}</p>` : ''}
      </div>
    </section>
  `
}

async function waitForRuntime(baseUrl: string) {
  const deadline = Date.now() + 45000
  let lastError = ''
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${baseUrl}/desktop/health`, { cache: 'no-store' })
      if (response.ok) {
        return
      }
      lastError = `${response.status} ${response.statusText}`
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error)
    }
    await new Promise((resolve) => setTimeout(resolve, 600))
  }
  throw new Error(lastError || 'runtime did not become ready')
}

async function boot() {
  render('Starting the embedded GTM Agent runtime and local ANIP services. No Docker is required for this desktop shell.')
  const baseUrl = await invoke<string>('gtm_agent_base_url')
  await waitForRuntime(baseUrl)
  window.location.href = `${baseUrl}/`
}

boot().catch((error) => {
  render(
    'GTM Agent runtime is unavailable.',
    error instanceof Error ? error.message : String(error),
  )
})
