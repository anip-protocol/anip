const app = document.querySelector<HTMLDivElement>('#app')

if (app) {
  app.innerHTML = `
    <section style="font-family: Avenir Next, Segoe UI, sans-serif; padding: 48px; color: #f4efe5; background: #101820; min-height: 100vh;">
      <p style="color: #f29d38; text-transform: uppercase; letter-spacing: .12em; font-size: 12px; font-weight: 800;">ANIP Showcase</p>
      <h1 style="font-size: 42px; margin: 8px 0;">GTM Agent Desktop</h1>
      <p style="max-width: 720px; line-height: 1.6; color: #c8d1da;">
        This desktop shell will start the embedded GTM Agent runtime and local ANIP services without Docker.
      </p>
    </section>
  `
}
