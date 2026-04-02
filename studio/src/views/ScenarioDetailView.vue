<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { designStore, setActivePack } from '../design/store'

const route = useRoute()
const router = useRouter()

const pack = computed(() => {
  const id = route.params.pack as string
  if (id) setActivePack(id)
  return designStore.packs.find(p => p.meta.id === id) ?? null
})

const context = computed(() => pack.value?.scenario?.scenario?.context ?? {})
const contextKeys = computed(() => Object.keys(context.value))

function navigateTo(view: string) {
  if (!pack.value) return
  router.push(`/design/${view}/${pack.value.meta.id}`)
}
</script>

<template>
  <div class="scenario-detail" v-if="pack">
    <div class="layout">
      <!-- Main content -->
      <div class="main">
        <h1 class="page-title">{{ pack.scenario.scenario.name }}</h1>
        <span class="category-badge">{{ pack.scenario.scenario.category }}</span>
        <div class="result-row" v-if="pack.meta.result">
          <span class="result-badge" :class="'result-' + pack.meta.result.toLowerCase().replace('_', '-')">
            {{ pack.meta.result }}
          </span>
        </div>
        <div class="result-row" v-else>
          <span class="result-badge result-none">Not evaluated</span>
        </div>

        <p class="narrative">{{ pack.scenario.scenario.narrative }}</p>

        <!-- Scenario Context -->
        <div class="section" v-if="contextKeys.length">
          <h2>Scenario Context</h2>
          <dl class="info-grid">
            <template v-for="key in contextKeys" :key="key">
              <dt>{{ key }}</dt>
              <dd>{{ typeof context[key] === 'object' ? JSON.stringify(context[key]) : context[key] }}</dd>
            </template>
          </dl>
        </div>

        <!-- Expected Behavior -->
        <div class="section">
          <h2>Expected Behavior</h2>
          <ul>
            <li v-for="(item, i) in pack.scenario.scenario.expected_behavior" :key="i">{{ item }}</li>
          </ul>
        </div>

        <!-- Expected ANIP Support -->
        <div class="section">
          <h2>Expected ANIP Support</h2>
          <ul>
            <li v-for="(item, i) in pack.scenario.scenario.expected_anip_support" :key="i">{{ item }}</li>
          </ul>
        </div>
      </div>

      <!-- Sidebar with quick links -->
      <aside class="quick-links">
        <h3>Pack Artifacts</h3>
        <button class="link-btn" @click="navigateTo('requirements')">
          <span class="link-icon">&#x1F4CB;</span> Requirements
        </button>
        <button class="link-btn" @click="navigateTo('proposal')" :disabled="!pack.proposal">
          <span class="link-icon">&#x1F4A1;</span> Proposal
        </button>
        <button class="link-btn" @click="navigateTo('evaluation')" :disabled="!pack.evaluation">
          <span class="link-icon">&#x2713;</span> Evaluation
        </button>
      </aside>
    </div>
  </div>
  <div v-else class="not-found">Pack not found.</div>
</template>

<style scoped>
.scenario-detail {
  padding: 2rem;
}

.layout {
  display: flex;
  gap: 2rem;
}

.main {
  flex: 1;
  min-width: 0;
  max-width: 720px;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
}

.category-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 2px 10px;
  border-radius: 10px;
  background: var(--accent-glow);
  color: var(--accent);
  margin-bottom: 0.5rem;
}

.result-row {
  margin-bottom: 1rem;
}

.result-badge {
  display: inline-block;
  font-size: 12px;
  font-weight: 700;
  padding: 3px 12px;
  border-radius: 12px;
}

.result-handled {
  background: rgba(52, 211, 153, 0.15);
  color: var(--design-handled, #34d399);
}

.result-partial {
  background: rgba(251, 191, 36, 0.15);
  color: var(--design-partial, #fbbf24);
}

.result-requires-glue {
  background: rgba(248, 113, 113, 0.15);
  color: var(--design-glue, #f87171);
}

.result-none {
  background: rgba(128, 128, 128, 0.15);
  color: var(--text-muted);
}

.narrative {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0 0 1.5rem;
}

.section {
  margin-bottom: 1.5rem;
}

.section h2 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
}

.section ul {
  list-style: disc;
  padding-left: 1.25rem;
  margin: 0;
}

.section li {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 0.25rem;
}

.info-grid {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 0.5rem 1rem;
  margin: 0;
}

.info-grid dt {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 500;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.info-grid dd {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
  word-break: break-word;
}

/* Quick links sidebar */
.quick-links {
  width: 200px;
  flex-shrink: 0;
  padding-top: 0.5rem;
}

.quick-links h3 {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
  margin: 0 0 0.75rem;
}

.link-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  margin-bottom: 4px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm, 6px);
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.link-btn:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-primary);
  border-color: var(--accent);
}

.link-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.link-icon {
  font-size: 14px;
  width: 20px;
  text-align: center;
}

.not-found {
  padding: 2rem;
  color: var(--text-muted);
}
</style>
