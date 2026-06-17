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

interface TemplateGroup {
  template_id: string
  latest: TemplateSummary
  versions: TemplateSummary[]
  total_downloads: number
}

function uniqueSorted(values: string[]): string[] {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean))).sort((a, b) => a.localeCompare(b))
}

function timestampValue(value: string): number {
  const time = new Date(value).getTime()
  return Number.isNaN(time) ? 0 : time
}

function versionSort(left: TemplateSummary, right: TemplateSummary): number {
  const publishedDelta = timestampValue(right.published_at) - timestampValue(left.published_at)
  if (publishedDelta !== 0) return publishedDelta
  return right.template_version.localeCompare(left.template_version, undefined, { numeric: true, sensitivity: 'base' })
}

function groupTemplates(records: TemplateSummary[]): TemplateGroup[] {
  const groups = new Map<string, TemplateSummary[]>()
  for (const item of records) {
    const versions = groups.get(item.template_id) ?? []
    versions.push(item)
    groups.set(item.template_id, versions)
  }
  return Array.from(groups.entries()).map(([template_id, versions]) => {
    const sortedVersions = [...versions].sort(versionSort)
    return {
      template_id,
      latest: sortedVersions[0],
      versions: sortedVersions,
      total_downloads: sortedVersions.reduce((total, item) => total + Number(item.download_count ?? 0), 0),
    }
  })
}

function templateTitle(item: TemplateSummary): string {
  return String(item.manifest?.template_title ?? item.template_id)
}

function templateSummary(item: TemplateSummary): string {
  return String(item.manifest?.template_summary ?? item.manifest?.summary ?? '')
}

function publisherBadgeLabel(item: TemplateSummary): string {
  const name = item.publisher?.display_name || item.publisher_id || 'Unknown publisher'
  const trust = item.publisher?.trust_level || item.publisher_type || 'unverified'
  return `${name} · ${trust.replace(/_/g, ' ')}`
}

function publisherBadgeClass(item: TemplateSummary): string {
  const trust = String(item.publisher?.trust_level ?? item.publisher_type ?? '').toLowerCase()
  return trust === 'official' ? 'official' : 'neutral'
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

const filteredGroups = computed(() => {
  const needle = query.value.trim().toLowerCase()
  const matchingItems = items.value.filter((item) => {
    if (!matchesText(item, needle)) return false
    if (kindFilter.value && item.template_kind !== kindFilter.value) return false
    if (specFilter.value && item.anip_spec_version !== specFilter.value) return false
    if (domainFilter.value && item.domain !== domainFilter.value) return false
    if (industryFilter.value && item.industry !== industryFilter.value) return false
    if (systemFilter.value && !(item.systems ?? []).includes(systemFilter.value)) return false
    return true
  })
  return groupTemplates(matchingItems)
})

const sortedGroups = computed(() => [...filteredGroups.value].sort((left, right) => {
  const downloadDelta = right.total_downloads - left.total_downloads
  if (downloadDelta !== 0) return downloadDelta
  const publishedDelta = timestampValue(right.latest.published_at) - timestampValue(left.latest.published_at)
  if (publishedDelta !== 0) return publishedDelta
  return left.template_id.localeCompare(right.template_id)
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
          {{ sortedGroups.length }} template{{ sortedGroups.length === 1 ? '' : 's' }}
          · {{ items.length }} immutable version{{ items.length === 1 ? '' : 's' }}
        </div>
      </div>

      <p class="immutability-note">
        Template versions are immutable records. This page groups them by template id for browsing; direct version links, package digests, publish timestamps, and download counts remain version-specific.
      </p>

      <p v-if="sortedGroups.length === 0" class="empty-state">No templates match these filters.</p>

      <div v-else class="card-grid">
        <article
          v-for="group in sortedGroups"
          :key="group.template_id"
          class="card template-card"
        >
          <div class="card-heading">
            <strong>{{ templateTitle(group.latest) }}</strong>
            <span :class="['authority-pill', publisherBadgeClass(group.latest)]">{{ publisherBadgeLabel(group.latest) }}</span>
          </div>
          <span class="template-id">{{ group.template_id }}</span>
          <span v-if="templateSummary(group.latest)" class="template-summary">{{ templateSummary(group.latest) }}</span>
          <span class="card-line">
            <b>Latest</b>
            <router-link
              class="card-line-value inline-link"
              :to="{ name: 'template-detail', params: { templateId: group.template_id, version: group.latest.template_version } }"
            >
              {{ group.latest.template_version }}
            </router-link>
          </span>
          <span class="card-line">
            <b>Kind</b>
            <span class="card-line-value">{{ group.latest.template_kind }}</span>
          </span>
          <span class="card-line">
            <b>Spec</b>
            <span class="card-line-value">{{ group.latest.anip_spec_version }}</span>
          </span>
          <span class="card-line">
            <b>Domain</b>
            <span class="card-line-value">{{ group.latest.domain || 'not declared' }}</span>
          </span>
          <span class="card-line">
            <b>Industry</b>
            <span class="card-line-value">{{ group.latest.industry || 'not declared' }}</span>
          </span>
          <span class="card-line">
            <b>Systems</b>
            <span class="card-line-value">{{ group.latest.systems?.length ? group.latest.systems.join(', ') : 'not declared' }}</span>
          </span>
          <span class="card-line">
            <b>Published</b>
            <span class="card-line-value">{{ formatRegistryTimestamp(group.latest.published_at) }}</span>
          </span>
          <span class="card-line">
            <b>Downloads</b>
            <span class="card-line-value">{{ group.total_downloads }} total · {{ group.latest.download_count ?? 0 }} latest</span>
          </span>
          <div class="version-history">
            <span class="version-history-title">Immutable versions</span>
            <router-link
              v-for="version in group.versions"
              :key="`${version.template_id}@${version.template_version}`"
              class="version-link"
              :to="{ name: 'template-detail', params: { templateId: version.template_id, version: version.template_version } }"
            >
              <span>{{ version.template_version }}</span>
              <small>{{ formatRegistryTimestamp(version.published_at) }} · {{ version.download_count ?? 0 }} downloads</small>
            </router-link>
          </div>
        </article>
      </div>
    </template>
  </section>
</template>
