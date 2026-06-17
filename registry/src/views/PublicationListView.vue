<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { listPublications, type PublicationSummary } from '../api'
import { formatRegistryTimestamp, formatTimestampRef } from '../datetime'

const loading = ref(true)
const error = ref<string | null>(null)
const items = ref<PublicationSummary[]>([])
const query = ref('')

interface PackageGroup {
  package_id: string
  latest: PublicationSummary
  versions: PublicationSummary[]
  total_downloads: number
}

function timestampValue(value: string): number {
  const time = new Date(value).getTime()
  return Number.isNaN(time) ? 0 : time
}

function versionSort(left: PublicationSummary, right: PublicationSummary): number {
  const publishedDelta = timestampValue(right.published_at) - timestampValue(left.published_at)
  if (publishedDelta !== 0) return publishedDelta
  return right.package_version.localeCompare(left.package_version, undefined, { numeric: true, sensitivity: 'base' })
}

function matchesPackage(item: PublicationSummary, needle: string): boolean {
  if (!needle) return true
  return [
    item.package_id,
    item.package_version,
    item.project_ref,
    item.product_revision_ref,
    item.developer_revision_ref,
    item.lineage?.product_revision?.artifact_id ?? '',
    String(item.lineage?.product_revision?.revision_number ?? ''),
    item.lineage?.developer_revision?.artifact_id ?? '',
    String(item.lineage?.developer_revision?.revision_number ?? ''),
    item.contract_signature,
  ].some((value) => value.toLowerCase().includes(needle))
}

function groupPackages(records: PublicationSummary[]): PackageGroup[] {
  const groups = new Map<string, PublicationSummary[]>()
  for (const item of records) {
    const versions = groups.get(item.package_id) ?? []
    versions.push(item)
    groups.set(item.package_id, versions)
  }
  return Array.from(groups.entries()).map(([package_id, versions]) => {
    const sortedVersions = [...versions].sort(versionSort)
    return {
      package_id,
      latest: sortedVersions[0],
      versions: sortedVersions,
      total_downloads: sortedVersions.reduce((total, item) => total + Number(item.download_count ?? 0), 0),
    }
  })
}

const filteredGroups = computed(() => {
  const needle = query.value.trim().toLowerCase()
  const matchingItems = items.value.filter((item) => matchesPackage(item, needle))
  return groupPackages(matchingItems)
})
const sortedGroups = computed(() => [...filteredGroups.value].sort((left, right) => {
  const downloadDelta = right.total_downloads - left.total_downloads
  if (downloadDelta !== 0) return downloadDelta
  const publishedDelta = timestampValue(right.latest.published_at) - timestampValue(left.latest.published_at)
  if (publishedDelta !== 0) return publishedDelta
  return left.package_id.localeCompare(right.package_id)
}))

function lineageLabel(item: PublicationSummary): string {
  const productRevision = item.lineage?.product_revision?.revision_number
  const developerRevision = item.lineage?.developer_revision?.revision_number
  const product = productRevision ? `Product r${productRevision}` : formatTimestampRef(item.product_revision_ref)
  const developer = developerRevision ? `Developer r${developerRevision}` : formatTimestampRef(item.developer_revision_ref)
  return `${product} -> ${developer}`
}

function publisherBadgeLabel(item: PublicationSummary): string {
  const name = item.publisher?.display_name || item.publisher_id || 'Unknown publisher'
  const trust = item.publisher?.trust_level || item.publisher_type || 'unverified'
  return `${name} · ${trust.replace(/_/g, ' ')}`
}

function publisherBadgeClass(item: PublicationSummary): string {
  const trust = String(item.publisher?.trust_level ?? item.publisher_type ?? '').toLowerCase()
  return trust === 'official' ? 'official' : 'neutral'
}

onMounted(async () => {
  try {
    items.value = await listPublications()
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
      <h1>Published Packages</h1>
      <p>Registry v1 starts by making selected Studio lineage portable and inspectable.</p>
    </div>

    <p v-if="loading">Loading publications…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <p v-else-if="items.length === 0">No published packages yet.</p>

    <template v-else>
      <div class="toolbar">
        <label class="search-field">
          <span>Search package, revision, signature</span>
          <input v-model="query" type="search" placeholder="work-item, developer-r5, sha256…" />
        </label>
        <div class="registry-count">
          {{ sortedGroups.length }} package{{ sortedGroups.length === 1 ? '' : 's' }}
          · {{ items.length }} immutable version{{ items.length === 1 ? '' : 's' }}
        </div>
      </div>

      <p class="immutability-note">
        Registry versions are immutable records. This page groups them by package id for browsing; direct version links, receipts, digests, timestamps, and download counts remain version-specific.
      </p>

      <p v-if="sortedGroups.length === 0" class="empty-state">No packages match this search.</p>

      <div v-else class="card-grid">
        <article
          v-for="group in sortedGroups"
          :key="group.package_id"
          class="card"
        >
          <div class="card-heading">
            <strong>{{ group.package_id }}</strong>
            <span :class="['authority-pill', publisherBadgeClass(group.latest)]">{{ publisherBadgeLabel(group.latest) }}</span>
          </div>
          <span class="card-line">
            <b>Latest</b>
            <router-link
              class="card-line-value inline-link"
              :to="{ name: 'package-detail', params: { packageId: group.package_id, version: group.latest.package_version } }"
            >
              {{ group.latest.package_version }}
            </router-link>
          </span>
          <span class="card-line">
            <b>Project</b>
            <span class="card-line-value">{{ group.latest.project_ref }}</span>
          </span>
          <span class="card-line">
            <b>Lineage</b>
            <span class="card-line-value">{{ lineageLabel(group.latest) }}</span>
          </span>
          <span class="card-line">
            <b>Published</b>
            <span class="card-line-value">{{ formatRegistryTimestamp(group.latest.published_at) }}</span>
          </span>
          <span class="card-line">
            <b>Downloads</b>
            <span class="card-line-value">{{ group.total_downloads }} total · {{ group.latest.download_count ?? 0 }} latest</span>
          </span>
          <span class="digest-line">{{ group.latest.contract_signature }}</span>
          <div class="version-history">
            <span class="version-history-title">Immutable versions</span>
            <router-link
              v-for="version in group.versions"
              :key="`${version.package_id}@${version.package_version}`"
              class="version-link"
              :to="{ name: 'package-detail', params: { packageId: version.package_id, version: version.package_version } }"
            >
              <span>{{ version.package_version }}</span>
              <small>{{ formatRegistryTimestamp(version.published_at) }} · {{ version.download_count ?? 0 }} downloads</small>
            </router-link>
          </div>
        </article>
      </div>
    </template>
  </section>
</template>
