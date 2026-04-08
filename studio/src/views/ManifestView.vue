<script setup lang="ts">
import { ref, watch, onMounted, computed } from 'vue'
import { useAnipManifest } from '@anip-dev/vue'
import { store } from '../store'
import StatusBadge from '../components/StatusBadge.vue'
import JsonPanel from '../components/JsonPanel.vue'
import CapabilityCard from '../components/CapabilityCard.vue'

const { data, loading, error, load: loadManifestData } = useAnipManifest()
const sigCopied = ref(false)
const manifestDoc = computed<any | null>(() => data.value as any)

async function load() {
  if (!store.connected) return
  try {
    await loadManifestData()
  } catch {
    // useAnipManifest already populates reactive error state
  }
}

onMounted(load)
watch(() => store.connected, (connected) => {
  if (connected) load()
  else { sigCopied.value = false }
})

const capabilities = computed(() => manifestDoc.value?.capabilities || {})
const signature = computed(() => manifestDoc.value?.signature || '')

function truncatedSig(sig: string): string {
  if (sig.length <= 40) return sig
  return sig.slice(0, 20) + '...' + sig.slice(-12)
}

async function copySig() {
  try {
    await navigator.clipboard.writeText(signature.value)
    sigCopied.value = true
    setTimeout(() => { sigCopied.value = false }, 1500)
  } catch { /* clipboard not available */ }
}
</script>

<template>
  <div class="view">
    <div class="view-header">
      <h2>Manifest</h2>
      <span class="view-subtitle">/anip/manifest</span>
    </div>

    <div v-if="!store.connected" class="placeholder">
      <div class="placeholder-icon">&#x1F4CB;</div>
      <p>Connect to an ANIP service to inspect its manifest and signature.</p>
    </div>

    <div v-else-if="loading" class="placeholder">
      <div class="spinner"></div>
      <p>Loading manifest...</p>
    </div>

    <div v-else-if="error" class="placeholder">
      <p class="error-text">{{ error }}</p>
      <button class="retry-btn" @click="load">Retry</button>
    </div>

    <div v-else-if="data" class="content-area">
      <!-- Signature -->
      <section class="section">
        <h3 class="section-title">Signature</h3>
        <div class="sig-row">
          <StatusBadge
            :label="signature ? 'Signature present' : 'No signature'"
            :type="signature ? 'success' : 'warning'"
          />
          <span v-if="signature" class="sig-value" :title="signature">{{ truncatedSig(signature) }}</span>
          <button v-if="signature" class="copy-btn" @click="copySig">
            {{ sigCopied ? 'Copied' : 'Copy' }}
          </button>
        </div>
      </section>

      <!-- Manifest Metadata -->
      <section class="section" v-if="manifestDoc?.manifestMetadata">
        <h3 class="section-title">Metadata</h3>
        <div class="meta-grid">
          <div class="meta-item">
            <span class="meta-label">Version</span>
            <span class="mono-value">{{ manifestDoc.manifestMetadata.version }}</span>
          </div>
          <div class="meta-item" v-if="manifestDoc.manifestMetadata.sha256">
            <span class="meta-label">SHA-256</span>
            <span class="mono-value hash-value">{{ manifestDoc.manifestMetadata.sha256 }}</span>
          </div>
          <div class="meta-item" v-if="manifestDoc.manifestMetadata.issued_at">
            <span class="meta-label">Issued</span>
            <span class="mono-value">{{ manifestDoc.manifestMetadata.issued_at }}</span>
          </div>
          <div class="meta-item" v-if="manifestDoc.manifestMetadata.expires_at">
            <span class="meta-label">Expires</span>
            <span class="mono-value">{{ manifestDoc.manifestMetadata.expires_at }}</span>
          </div>
        </div>
      </section>

      <!-- Service Identity -->
      <section class="section" v-if="manifestDoc?.serviceIdentity">
        <h3 class="section-title">Service Identity</h3>
        <div class="meta-grid">
          <div class="meta-item">
            <span class="meta-label">ID</span>
            <span class="mono-value">{{ manifestDoc.serviceIdentity.id }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">JWKS URI</span>
            <span class="mono-value">{{ manifestDoc.serviceIdentity.jwks_uri }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Issuer Mode</span>
            <span class="mono-value">{{ manifestDoc.serviceIdentity.issuer_mode }}</span>
          </div>
        </div>
      </section>

      <!-- Trust -->
      <section class="section" v-if="manifestDoc?.trust">
        <h3 class="section-title">Trust</h3>
        <div class="meta-grid">
          <div class="meta-item">
            <span class="meta-label">Level</span>
            <StatusBadge :label="manifestDoc.trust.level" :type="manifestDoc.trust.level === 'signed' ? 'info' : 'success'" />
          </div>
          <div class="meta-item" v-if="manifestDoc.trust.anchoring?.cadence">
            <span class="meta-label">Cadence</span>
            <span class="mono-value">{{ manifestDoc.trust.anchoring.cadence }}</span>
          </div>
        </div>
      </section>

      <!-- Capabilities -->
      <section class="section">
        <h3 class="section-title">Capabilities ({{ Object.keys(capabilities).length }})</h3>
        <div class="caps-list">
          <CapabilityCard
            v-for="(cap, name) in capabilities"
            :key="name"
            :name="String(name)"
            :capability="cap.raw || cap"
          />
        </div>
      </section>

      <!-- Raw JSON -->
      <section class="section">
        <JsonPanel :data="manifestDoc?.raw || data" title="Raw Manifest" :collapsed="true" />
      </section>
    </div>
  </div>
</template>

<style scoped>
.view {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.view-header {
  padding: 24px 32px 16px;
  border-bottom: 1px solid var(--border);
}

.view-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.view-subtitle {
  font-size: 13px;
  color: var(--text-muted);
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: var(--text-muted);
}

.placeholder-icon {
  font-size: 48px;
  opacity: 0.4;
}

.placeholder p {
  font-size: 14px;
  max-width: 320px;
  text-align: center;
  line-height: 1.5;
}

.error-text {
  color: var(--error) !important;
}

.retry-btn {
  padding: 6px 16px;
  background: var(--accent);
  border: none;
  border-radius: var(--radius-sm);
  color: #fff;
  font-size: 13px;
  cursor: pointer;
}

.retry-btn:hover {
  background: var(--accent-hover);
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.content-area {
  flex: 1;
  padding: 24px 32px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0;
}

/* Signature */
.sig-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sig-value {
  font-size: 12px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: var(--text-secondary);
  user-select: all;
  padding: 4px 10px;
  background: var(--bg-hover);
  border-radius: 4px;
}

.copy-btn {
  padding: 3px 10px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 11px;
  cursor: pointer;
  transition: all 150ms ease;
}

.copy-btn:hover {
  background: var(--bg-input);
  color: var(--text-primary);
  border-color: var(--accent);
}

/* Metadata */
.meta-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 32px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.meta-label {
  font-size: 12px;
  color: var(--text-muted);
}

.mono-value {
  font-size: 13px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: var(--text-primary);
}

.hash-value {
  font-size: 11px;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  user-select: all;
}

/* Capabilities */
.caps-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
