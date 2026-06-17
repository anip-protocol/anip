<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getTemplate, templateDownloadURL, type RegistryTemplateRecord } from '../api'
import { formatRegistryTimestamp } from '../datetime'

const props = defineProps<{
  templateId: string
  version: string
}>()

const loading = ref(true)
const error = ref<string | null>(null)
const record = ref<RegistryTemplateRecord | null>(null)

function asRecordArray(value: unknown): Record<string, any>[] {
  return Array.isArray(value)
    ? value
        .map((item) => item && typeof item === 'object' ? item as Record<string, any> : null)
        .filter((item): item is Record<string, any> => Boolean(item))
    : []
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => String(item ?? '').trim()).filter(Boolean)
    : []
}

function text(value: unknown, fallback = ''): string {
  const result = String(value ?? '').trim()
  return result || fallback
}

const title = computed(() => text(record.value?.manifest?.template_title, props.templateId))
const summary = computed(() => text(record.value?.manifest?.template_summary ?? record.value?.manifest?.summary))
const documents = computed(() => asRecordArray(record.value?.template?.documents))
const connections = computed(() => asRecordArray(record.value?.template?.connections))
const discoveryRecords = computed(() => asRecordArray(record.value?.template?.discoveryRecords))
const capabilityMappings = computed(() => asRecordArray(record.value?.template?.capabilityMappings))
const systems = computed(() => {
  const declared = record.value?.systems ?? []
  return declared.length ? declared : asStringArray(record.value?.manifest?.systems)
})
const manifestJson = computed(() => JSON.stringify(record.value?.manifest ?? {}, null, 2))
const templateJson = computed(() => JSON.stringify(record.value?.template ?? {}, null, 2))
const packageJson = computed(() => JSON.stringify(record.value?.package ?? {}, null, 2))
const downloadHref = computed(() => templateDownloadURL(props.templateId, props.version))
const publisherLabel = computed(() => {
  const publisher = record.value?.publisher
  if (publisher?.display_name) return publisher.display_name
  return record.value?.publisher_id || 'Unknown publisher'
})
const publisherTrustLabel = computed(() => {
  const publisher = record.value?.publisher
  if (publisher?.trust_level) return publisher.trust_level.replace(/_/g, ' ')
  return record.value?.publisher_type || 'unverified'
})
const publisherTrustClass = computed(() => {
  const trust = String(record.value?.publisher?.trust_level ?? record.value?.publisher_type ?? '').toLowerCase()
  return trust === 'official' ? 'official' : 'neutral'
})

onMounted(async () => {
  try {
    record.value = await getTemplate(props.templateId, props.version)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="page">
    <router-link class="back-link" to="/templates">← Back to templates</router-link>

    <p v-if="loading">Loading template…</p>
    <p v-else-if="error" class="error">{{ error }}</p>

    <template v-else-if="record">
      <section class="hero-panel template-hero">
        <div>
          <span class="eyebrow">Starter Template</span>
          <h2>{{ title }} <span>@{{ record.template_version }}</span></h2>
          <p v-if="summary">{{ summary }}</p>
          <p v-else>Reusable Studio project seed material. Review source documents and connection references before creating a project from this template.</p>
        </div>
        <div class="hero-badges">
          <span :class="['authority-pill', publisherTrustClass]">
            {{ publisherLabel }} · {{ publisherTrustLabel }}
          </span>
          <span class="authority-pill neutral">{{ record.template_kind }}</span>
          <span class="authority-pill remote">{{ record.anip_spec_version }}</span>
        </div>
      </section>

      <section class="metric-grid">
        <div class="metric-card">
          <span>Downloads</span>
          <strong>{{ record.download_count ?? 0 }}</strong>
        </div>
        <div class="metric-card">
          <span>Documents</span>
          <strong>{{ documents.length }}</strong>
        </div>
        <div class="metric-card">
          <span>Connections</span>
          <strong>{{ connections.length }}</strong>
        </div>
        <div class="metric-card">
          <span>Systems</span>
          <code>{{ systems.length ? systems.join(', ') : 'not declared' }}</code>
        </div>
      </section>

      <section class="detail-grid">
        <article class="panel package-overview-panel">
          <h2>Template Overview</h2>
          <dl class="kv-list">
            <dt>Template ID</dt>
            <dd><code>{{ record.template_id }}</code></dd>
            <dt>Project Type</dt>
            <dd>{{ record.project_type }}</dd>
            <dt>Domain</dt>
            <dd>{{ record.domain || 'not declared' }}</dd>
            <dt>Industry</dt>
            <dd>{{ record.industry || 'not declared' }}</dd>
            <dt>Published</dt>
            <dd>{{ formatRegistryTimestamp(record.published_at) }}</dd>
          </dl>
        </article>

        <article class="panel">
          <h2>Integrity</h2>
          <dl class="kv-list">
            <dt>Manifest Digest</dt>
            <dd><code>{{ record.manifest_digest }}</code></dd>
            <dt>Template Digest</dt>
            <dd><code>{{ record.template_digest }}</code></dd>
            <dt>Package Digest</dt>
            <dd><code>{{ record.package_digest }}</code></dd>
          </dl>
          <a class="artifact-action" :href="downloadHref">Download template package</a>
        </article>

        <article class="panel full-width-panel">
          <h2>What This Template Contains</h2>
          <p class="tooling-note">Templates are project-starting material, not generated runtime packages. They may include Markdown source docs, non-secret connection references, discovery records, and capability mapping seed data.</p>
          <div class="template-content-grid">
            <div class="template-content-card">
              <strong>Markdown source docs</strong>
              <span>{{ documents.length }}</span>
            </div>
            <div class="template-content-card">
              <strong>Connection refs</strong>
              <span>{{ connections.length }}</span>
            </div>
            <div class="template-content-card">
              <strong>Discovery records</strong>
              <span>{{ discoveryRecords.length }}</span>
            </div>
            <div class="template-content-card">
              <strong>Capability mappings</strong>
              <span>{{ capabilityMappings.length }}</span>
            </div>
          </div>
        </article>

        <article v-if="documents.length" class="panel full-width-panel">
          <h2>Source Documents</h2>
          <div class="resource-section">
            <div v-for="document in documents" :key="String(document.filename ?? document.idSuffix)" class="material-card">
              <strong>{{ text(document.title, 'Untitled document') }}</strong>
              <span><code>{{ document.filename }}</code></span>
              <span>{{ text(document.kind, 'source_doc') }}</span>
            </div>
          </div>
        </article>

        <article v-if="connections.length" class="panel full-width-panel">
          <h2>Connection References</h2>
          <div class="resource-section">
            <div v-for="connection in connections" :key="String(connection.idSuffix ?? connection.connection_ref ?? connection.display_name)" class="material-card">
              <strong>{{ text(connection.display_name, text(connection.system_kind, 'Connection')) }}</strong>
              <span>{{ text(connection.backend_kind, 'backend') }} · {{ text(connection.system_kind, 'system') }} · {{ text(connection.auth_mode, 'auth') }}</span>
              <span>Endpoint ref: <code>{{ text(connection.endpoint_ref, 'not declared') }}</code></span>
              <span>Secret ref: <code>{{ text(connection.secret_ref, 'not declared') }}</code></span>
            </div>
          </div>
        </article>

        <article class="panel artifact-panel full-width-panel">
          <details>
            <summary class="artifact-header">
              <h2>Manifest JSON</h2>
              <span>review metadata</span>
            </summary>
            <pre>{{ manifestJson }}</pre>
          </details>
        </article>

        <article class="panel artifact-panel full-width-panel">
          <details>
            <summary class="artifact-header">
              <h2>Template JSON</h2>
              <span>starter payload</span>
            </summary>
            <pre>{{ templateJson }}</pre>
          </details>
        </article>

        <article class="panel artifact-panel full-width-panel">
          <details>
            <summary class="artifact-header">
              <h2>Template Package JSON</h2>
              <span>download envelope</span>
            </summary>
            <pre>{{ packageJson }}</pre>
          </details>
        </article>
      </section>
    </template>
  </section>
</template>
