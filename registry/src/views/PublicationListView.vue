<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { listPublications, type PublicationSummary } from '../api'
import { formatRegistryTimestamp, formatTimestampRef } from '../datetime'

const loading = ref(true)
const error = ref<string | null>(null)
const items = ref<PublicationSummary[]>([])
const query = ref('')

const filteredItems = computed(() => {
  const needle = query.value.trim().toLowerCase()
  if (!needle) return items.value
  return items.value.filter((item) => [
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
  ].some((value) => value.toLowerCase().includes(needle)))
})
const sortedItems = computed(() => [...filteredItems.value].sort((left, right) => {
  const downloadDelta = Number(right.download_count ?? 0) - Number(left.download_count ?? 0)
  if (downloadDelta !== 0) return downloadDelta
  const publishedDelta = new Date(right.published_at).getTime() - new Date(left.published_at).getTime()
  if (publishedDelta !== 0 && !Number.isNaN(publishedDelta)) return publishedDelta
  const packageDelta = left.package_id.localeCompare(right.package_id)
  if (packageDelta !== 0) return packageDelta
  return right.package_version.localeCompare(left.package_version)
}))

function lineageLabel(item: PublicationSummary): string {
  const productRevision = item.lineage?.product_revision?.revision_number
  const developerRevision = item.lineage?.developer_revision?.revision_number
  const product = productRevision ? `Product r${productRevision}` : formatTimestampRef(item.product_revision_ref)
  const developer = developerRevision ? `Developer r${developerRevision}` : formatTimestampRef(item.developer_revision_ref)
  return `${product} -> ${developer}`
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
          {{ sortedItems.length }} of {{ items.length }} package{{ items.length === 1 ? '' : 's' }}
        </div>
      </div>

      <p v-if="sortedItems.length === 0" class="empty-state">No packages match this search.</p>

      <div v-else class="card-grid">
      <router-link
        v-for="item in sortedItems"
        :key="`${item.package_id}@${item.package_version}`"
        class="card"
        :to="{ name: 'package-detail', params: { packageId: item.package_id, version: item.package_version } }"
      >
        <div class="card-heading">
          <strong>{{ item.package_id }}@{{ item.package_version }}</strong>
          <span class="authority-pill remote">Registry</span>
        </div>
        <span class="card-line">
          <b>Project</b>
          <span class="card-line-value">{{ item.project_ref }}</span>
        </span>
        <span class="card-line">
          <b>Lineage</b>
          <span class="card-line-value">{{ lineageLabel(item) }}</span>
        </span>
        <span class="card-line">
          <b>Published</b>
          <span class="card-line-value">{{ formatRegistryTimestamp(item.published_at) }}</span>
        </span>
        <span class="card-line">
          <b>Downloads</b>
          <span class="card-line-value">{{ item.download_count ?? 0 }}</span>
        </span>
        <span class="digest-line">{{ item.contract_signature }}</span>
      </router-link>
      </div>
    </template>
  </section>
</template>
