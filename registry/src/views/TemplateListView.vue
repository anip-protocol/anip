<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { listTemplates, type TemplateSummary } from '../api'
import { formatRegistryTimestamp } from '../datetime'

const loading = ref(true)
const error = ref<string | null>(null)
const items = ref<TemplateSummary[]>([])
const query = ref('')
const kindFilter = ref('')
const specFilter = ref('')
const domainFilter = ref('')
const industryFilter = ref('')
const systemFilter = ref('')

function uniqueSorted(values: string[]): string[] {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean))).sort((a, b) => a.localeCompare(b))
}

function templateTitle(item: TemplateSummary): string {
  return String(item.manifest?.template_title ?? item.template_id)
}

function templateSummary(item: TemplateSummary): string {
  return String(item.manifest?.template_summary ?? item.manifest?.summary ?? '')
}

function matchesText(item: TemplateSummary, needle: string): boolean {
  if (!needle) return true
  return [
    item.template_id,
    item.template_version,
    item.template_kind,
    item.project_type,
    item.anip_spec_version,
    item.domain ?? '',
    item.industry ?? '',
    ...(item.systems ?? []),
    templateTitle(item),
    templateSummary(item),
  ].some((value) => value.toLowerCase().includes(needle))
}

const kindOptions = computed(() => uniqueSorted(items.value.map((item) => item.template_kind)))
const specOptions = computed(() => uniqueSorted(items.value.map((item) => item.anip_spec_version)))
const domainOptions = computed(() => uniqueSorted(items.value.map((item) => item.domain ?? '')))
const industryOptions = computed(() => uniqueSorted(items.value.map((item) => item.industry ?? '')))
const systemOptions = computed(() => uniqueSorted(items.value.flatMap((item) => item.systems ?? [])))

const filteredItems = computed(() => {
  const needle = query.value.trim().toLowerCase()
  return items.value.filter((item) => {
    if (!matchesText(item, needle)) return false
    if (kindFilter.value && item.template_kind !== kindFilter.value) return false
    if (specFilter.value && item.anip_spec_version !== specFilter.value) return false
    if (domainFilter.value && item.domain !== domainFilter.value) return false
    if (industryFilter.value && item.industry !== industryFilter.value) return false
    if (systemFilter.value && !(item.systems ?? []).includes(systemFilter.value)) return false
    return true
  })
})

const sortedItems = computed(() => [...filteredItems.value].sort((left, right) => {
  const downloadDelta = Number(right.download_count ?? 0) - Number(left.download_count ?? 0)
  if (downloadDelta !== 0) return downloadDelta
  const publishedDelta = new Date(right.published_at).getTime() - new Date(left.published_at).getTime()
  if (publishedDelta !== 0 && !Number.isNaN(publishedDelta)) return publishedDelta
  const templateDelta = left.template_id.localeCompare(right.template_id)
  if (templateDelta !== 0) return templateDelta
  return right.template_version.localeCompare(left.template_version)
}))

onMounted(async () => {
  try {
    items.value = await listTemplates()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="page">
    <div class="page-header">
      <h1>Starter Templates</h1>
      <p>Reusable Studio project seeds for governed service and fronting flows. Templates are separate from published ANIP service packages.</p>
    </div>

    <p v-if="loading">Loading templates…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <p v-else-if="items.length === 0">No starter templates yet.</p>

    <template v-else>
      <div class="toolbar template-toolbar">
        <label class="search-field">
          <span>Search template, domain, system</span>
          <input v-model="query" type="search" placeholder="fronting, jira, saas…" />
        </label>
        <label class="filter-field">
          <span>Kind</span>
          <select v-model="kindFilter">
            <option value="">All kinds</option>
            <option v-for="option in kindOptions" :key="option" :value="option">{{ option }}</option>
          </select>
        </label>
        <label class="filter-field">
          <span>Spec</span>
          <select v-model="specFilter">
            <option value="">All specs</option>
            <option v-for="option in specOptions" :key="option" :value="option">{{ option }}</option>
          </select>
        </label>
        <label class="filter-field">
          <span>Domain</span>
          <select v-model="domainFilter">
            <option value="">All domains</option>
            <option v-for="option in domainOptions" :key="option" :value="option">{{ option }}</option>
          </select>
        </label>
        <label class="filter-field">
          <span>Industry</span>
          <select v-model="industryFilter">
            <option value="">All industries</option>
            <option v-for="option in industryOptions" :key="option" :value="option">{{ option }}</option>
          </select>
        </label>
        <label class="filter-field">
          <span>System</span>
          <select v-model="systemFilter">
            <option value="">All systems</option>
            <option v-for="option in systemOptions" :key="option" :value="option">{{ option }}</option>
          </select>
        </label>
        <div class="registry-count">
          {{ sortedItems.length }} of {{ items.length }} template{{ items.length === 1 ? '' : 's' }}
        </div>
      </div>

      <p v-if="sortedItems.length === 0" class="empty-state">No templates match these filters.</p>

      <div v-else class="card-grid">
        <router-link
          v-for="item in sortedItems"
          :key="`${item.template_id}@${item.template_version}`"
          class="card template-card"
          :to="{ name: 'template-detail', params: { templateId: item.template_id, version: item.template_version } }"
        >
          <div class="card-heading">
            <strong>{{ templateTitle(item) }}</strong>
            <span class="authority-pill neutral">Template</span>
          </div>
          <span class="template-id">{{ item.template_id }}@{{ item.template_version }}</span>
          <span v-if="templateSummary(item)" class="template-summary">{{ templateSummary(item) }}</span>
          <span class="card-line">
            <b>Kind</b>
            <span class="card-line-value">{{ item.template_kind }}</span>
          </span>
          <span class="card-line">
            <b>Spec</b>
            <span class="card-line-value">{{ item.anip_spec_version }}</span>
          </span>
          <span class="card-line">
            <b>Domain</b>
            <span class="card-line-value">{{ item.domain || 'not declared' }}</span>
          </span>
          <span class="card-line">
            <b>Industry</b>
            <span class="card-line-value">{{ item.industry || 'not declared' }}</span>
          </span>
          <span class="card-line">
            <b>Systems</b>
            <span class="card-line-value">{{ item.systems?.length ? item.systems.join(', ') : 'not declared' }}</span>
          </span>
          <span class="card-line">
            <b>Published</b>
            <span class="card-line-value">{{ formatRegistryTimestamp(item.published_at) }}</span>
          </span>
          <span class="card-line">
            <b>Downloads</b>
            <span class="card-line-value">{{ item.download_count ?? 0 }}</span>
          </span>
        </router-link>
      </div>
    </template>
  </section>
</template>
