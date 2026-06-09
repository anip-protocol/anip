<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

function goInspect() {
  router.push('/inspect/discovery')
}

function goDesign() {
  router.push('/design')
}
</script>

<template>
  <div class="studio-home">
    <div class="home-hero">
      <div class="hero-icon">&#x25C6;</div>
      <h1 class="hero-title">ANIP <span class="hero-accent">Studio</span></h1>
      <p class="hero-subtitle">Design, validate, and inspect governed agent-facing capabilities</p>
    </div>

    <div class="entry-cards">
      <div class="entry-card" @click="goInspect">
        <div class="card-icon card-icon-inspect" aria-hidden="true">
          <svg class="card-icon-svg" viewBox="0 0 64 64" fill="none">
            <rect x="10" y="12" width="30" height="24" rx="8" class="icon-panel" />
            <path d="M18 22h14M18 28h9" class="icon-line" />
            <circle cx="41" cy="39" r="9" class="icon-ring" />
            <path d="m47.5 45.5 6.5 6.5" class="icon-handle" />
          </svg>
        </div>
        <h2 class="card-title">Invoke & Inspect</h2>
        <p class="card-desc">Connect to a service to invoke capabilities, inspect protocol surfaces, audit traces, and runtime evidence</p>
        <button class="card-btn" @click.stop="goInspect">Connect</button>
      </div>

      <div class="entry-card" @click="goDesign">
        <div class="card-icon card-icon-design" aria-hidden="true">
          <svg class="card-icon-svg" viewBox="0 0 64 64" fill="none">
            <rect x="12" y="14" width="18" height="18" rx="6" class="icon-panel" />
            <rect x="34" y="18" width="18" height="18" rx="6" class="icon-panel icon-panel-secondary" />
            <rect x="23" y="36" width="18" height="14" rx="6" class="icon-panel icon-panel-tertiary" />
            <path d="M30 25h4M27 43h10M30 32l6 4M24 32l5 4" class="icon-line" />
          </svg>
        </div>
        <h2 class="card-title">Design</h2>
        <p class="card-desc">Work through the full project flow: source documents, product design, developer design, and verification</p>
        <button class="card-btn card-btn-design" @click.stop="goDesign">Browse</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.studio-home {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 2rem;
  text-align: center;
}

.home-hero {
  margin-bottom: 3rem;
}

.hero-icon {
  font-size: 56px;
  color: var(--accent);
  margin-bottom: 1rem;
  opacity: 0.7;
}

.hero-title {
  font-size: 32px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
  letter-spacing: -0.5px;
}

.hero-accent {
  color: var(--accent);
  font-weight: 500;
}

.hero-subtitle {
  font-size: 15px;
  color: var(--text-secondary);
  margin: 0;
  max-width: 440px;
  line-height: 1.6;
}

.entry-cards {
  display: flex;
  gap: 24px;
  max-width: 520px;
  width: 100%;
}

.entry-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 2rem 1.5rem;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  cursor: pointer;
  transition: all var(--transition);
  text-align: center;
}

.entry-card:hover {
  border-color: var(--accent);
  background: var(--bg-hover);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
}

.card-icon {
  margin-bottom: 1rem;
  width: 72px;
  height: 72px;
  display: grid;
  place-items: center;
  border-radius: 22px;
  border: 1px solid var(--surface-border-card);
  background:
    radial-gradient(circle at 30% 20%, rgba(148, 163, 184, 0.22), transparent 55%),
    linear-gradient(180deg, rgba(30, 41, 59, 0.96), rgba(15, 23, 42, 0.9));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.04),
    0 12px 28px rgba(15, 23, 42, 0.22);
}

.card-icon-inspect {
  color: #93c5fd;
}

.card-icon-design {
  color: #67e8f9;
}

.card-icon-svg {
  width: 42px;
  height: 42px;
}

.icon-panel {
  fill: rgba(148, 163, 184, 0.12);
  stroke: currentColor;
  stroke-width: 2.4;
}

.icon-panel-secondary {
  fill: rgba(59, 130, 246, 0.12);
}

.icon-panel-tertiary {
  fill: rgba(34, 197, 94, 0.12);
}

.icon-line,
.icon-ring,
.icon-handle {
  stroke: currentColor;
  stroke-width: 2.6;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.entry-card:hover .card-icon {
  transform: translateY(-1px) scale(1.02);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.06),
    0 16px 32px rgba(15, 23, 42, 0.28);
}

.card-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
}

.card-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0 0 1.5rem;
  flex: 1;
}

.card-btn {
  height: 38px;
  padding: 0 28px;
  background: var(--accent);
  border: none;
  border-radius: var(--radius-sm);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition);
}

.card-btn:hover {
  background: var(--accent-hover);
}

.card-btn-design {
  background: var(--accent);
}

@media (max-width: 600px) {
  .entry-cards {
    flex-direction: column;
  }
}
</style>
