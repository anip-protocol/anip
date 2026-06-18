<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  listAdminArtifacts,
  listAdminNamespaces,
  listAdminPublishers,
  updateAdminArtifactStatus,
  updateAdminNamespaceStatus,
  updateAdminPublisherStatus,
  type PublisherArtifactSummary,
  type RegistryNamespaceSummary,
  type RegistryPublisher,
} from '../api'
import { formatRegistryTimestamp } from '../datetime'

const STORAGE_KEY = 'anip_registry_admin_token'

const tokenInput = ref('')
const activeToken = ref('')
const loading = ref(false)
const error = ref<string | null>(null)
const success = ref<string | null>(null)
const namespaces = ref<RegistryNamespaceSummary[]>([])
const publishers = ref<RegistryPublisher[]>([])
const artifacts = ref<PublisherArtifactSummary[]>([])

const namespaceActions = reactive<Record<string, { status: string; reason: string }>>({})
const publisherActions = reactive<Record<string, { status: string; trustLevel: string; reason: string }>>({})
const artifactActions = reactive<Record<string, { status: string; reason: string }>>({})

const hasActiveToken = computed(() => activeToken.value.trim() !== '')
const pendingNamespaces = computed(() => namespaces.value.filter((namespace) => namespace.status === 'pending_verification'))
const suspendedPublishers = computed(() => publishers.value.filter((publisher) => publisher.status === 'suspended'))
const suspendedArtifacts = computed(() => artifacts.value.filter((artifact) => artifact.status === 'suspended'))

function artifactKey(artifact: PublisherArtifactSummary): string {
  return `${artifact.artifact_kind}:${artifact.artifact_id}`
}

function ensureNamespaceAction(namespace: RegistryNamespaceSummary): { status: string; reason: string } {
  if (!namespaceActions[namespace.namespace]) {
    namespaceActions[namespace.namespace] = {
      status: namespace.status,
      reason: '',
    }
  }
  return namespaceActions[namespace.namespace]
}

function ensurePublisherAction(publisher: RegistryPublisher): { status: string; trustLevel: string; reason: string } {
  if (!publisherActions[publisher.publisher_id]) {
    publisherActions[publisher.publisher_id] = {
      status: publisher.status,
      trustLevel: publisher.trust_level,
      reason: '',
    }
  }
  return publisherActions[publisher.publisher_id]
}

function ensureArtifactAction(artifact: PublisherArtifactSummary): { status: string; reason: string } {
  const key = artifactKey(artifact)
  if (!artifactActions[key]) {
    artifactActions[key] = {
      status: artifact.status,
      reason: '',
    }
  }
  return artifactActions[key]
}

function syncActionDefaults(): void {
  namespaces.value.forEach((namespace) => {
    const action = ensureNamespaceAction(namespace)
    action.status = namespace.status
  })
  publishers.value.forEach((publisher) => {
    const action = ensurePublisherAction(publisher)
    action.status = publisher.status
    action.trustLevel = publisher.trust_level
  })
  artifacts.value.forEach((artifact) => {
    const action = ensureArtifactAction(artifact)
    action.status = artifact.status
  })
}

async function loadAdminState(token: string): Promise<void> {
  loading.value = true
  error.value = null
  success.value = null
  try {
    const [namespaceResult, publisherResult, artifactResult] = await Promise.all([
      listAdminNamespaces(token),
      listAdminPublishers(token),
      listAdminArtifacts(token),
    ])
    activeToken.value = token
    tokenInput.value = token
    namespaces.value = namespaceResult
    publishers.value = publisherResult
    artifacts.value = artifactResult
    syncActionDefaults()
    localStorage.setItem(STORAGE_KEY, token)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

async function connect(): Promise<void> {
  const token = tokenInput.value.trim()
  if (!token) {
    error.value = 'Paste the Registry admin token first.'
    return
  }
  await loadAdminState(token)
}

function disconnect(): void {
  activeToken.value = ''
  tokenInput.value = ''
  namespaces.value = []
  publishers.value = []
  artifacts.value = []
  error.value = null
  success.value = null
  localStorage.removeItem(STORAGE_KEY)
}

async function refresh(): Promise<void> {
  if (!hasActiveToken.value) return
  await loadAdminState(activeToken.value)
}

async function updateNamespace(namespace: RegistryNamespaceSummary): Promise<void> {
  if (!activeToken.value) return
  error.value = null
  success.value = null
  const action = ensureNamespaceAction(namespace)
  try {
    await updateAdminNamespaceStatus(activeToken.value, namespace.namespace, {
      status: action.status,
      reason: action.reason.trim() || undefined,
    })
    action.reason = ''
    success.value = `Namespace ${namespace.namespace} updated.`
    await refresh()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function updatePublisher(publisher: RegistryPublisher): Promise<void> {
  if (!activeToken.value) return
  error.value = null
  success.value = null
  const action = ensurePublisherAction(publisher)
  try {
    await updateAdminPublisherStatus(activeToken.value, publisher.publisher_id, {
      status: action.status,
      trust_level: action.trustLevel,
      reason: action.reason.trim() || undefined,
    })
    action.reason = ''
    success.value = `Publisher ${publisher.publisher_id} updated.`
    await refresh()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function updateArtifact(artifact: PublisherArtifactSummary): Promise<void> {
  if (!activeToken.value) return
  error.value = null
  success.value = null
  const action = ensureArtifactAction(artifact)
  try {
    await updateAdminArtifactStatus(activeToken.value, artifact.artifact_kind, artifact.artifact_id, {
      status: action.status,
      reason: action.reason.trim() || undefined,
    })
    action.reason = ''
    success.value = `${artifact.artifact_kind} ${artifact.artifact_id} updated.`
    await refresh()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

onMounted(() => {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved) {
    tokenInput.value = saved
    void loadAdminState(saved)
  }
})
</script>

<template>
  <section class="page">
    <div class="page-header">
      <h1>Registry Admin</h1>
      <p>Moderate namespace verification, publisher status, and package or template ownership. This page uses the configured Registry admin bearer token locally in your browser.</p>
    </div>

    <section class="hero-panel publisher-auth-panel">
      <div>
        <span class="eyebrow">Admin Moderation</span>
        <h2>Connect with the admin token</h2>
        <p>The admin token is configured server-side through <code>ANIP_REGISTRY_ADMIN_TOKEN</code>. The UI never creates an admin session.</p>
      </div>
      <div class="publisher-token-form">
        <label class="form-field">
          <span>Admin bearer token</span>
          <input v-model="tokenInput" type="password" autocomplete="off" placeholder="admin token" />
        </label>
        <div class="action-row">
          <button class="artifact-action" type="button" :disabled="loading" @click="connect">
            {{ loading ? 'Connecting…' : 'Connect' }}
          </button>
          <button v-if="hasActiveToken" class="artifact-action secondary" type="button" :disabled="loading" @click="refresh">
            Refresh
          </button>
          <button v-if="hasActiveToken" class="artifact-action secondary" type="button" @click="disconnect">
            Disconnect
          </button>
        </div>
      </div>
    </section>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="success" class="success-note">{{ success }}</p>

    <template v-if="hasActiveToken">
      <section class="metric-grid">
        <div class="metric-card">
          <span>Pending Namespaces</span>
          <strong>{{ pendingNamespaces.length }}</strong>
        </div>
        <div class="metric-card">
          <span>Publishers</span>
          <strong>{{ publishers.length }}</strong>
        </div>
        <div class="metric-card">
          <span>Suspended Publishers</span>
          <strong>{{ suspendedPublishers.length }}</strong>
        </div>
        <div class="metric-card">
          <span>Suspended Artifacts</span>
          <strong>{{ suspendedArtifacts.length }}</strong>
        </div>
      </section>

      <section class="detail-grid">
        <article class="panel full-width-panel">
          <h2>Namespace Verification</h2>
          <p class="tooling-note">Approve, reject, reserve, or suspend namespaces. Pending verification entries are sorted first by the backend.</p>
          <p v-if="namespaces.length === 0" class="empty-state">No namespaces found.</p>
          <div v-else class="admin-table">
            <div v-for="namespace in namespaces" :key="namespace.namespace" class="admin-row">
              <div>
                <strong>{{ namespace.namespace }}</strong>
                <span>{{ namespace.status }} · publisher <code>{{ namespace.publisher_id }}</code> · {{ namespace.artifact_kinds.join(', ') }}</span>
                <span>Updated {{ formatRegistryTimestamp(namespace.updated_at) }}</span>
              </div>
              <form class="admin-action-form" @submit.prevent="updateNamespace(namespace)">
                <label class="form-field">
                  <span>Status</span>
                  <select v-model="ensureNamespaceAction(namespace).status">
                    <option value="pending_verification">pending_verification</option>
                    <option value="active">active</option>
                    <option value="reserved">reserved</option>
                    <option value="suspended">suspended</option>
                    <option value="rejected">rejected</option>
                  </select>
                </label>
                <label class="form-field">
                  <span>Reason</span>
                  <input v-model="ensureNamespaceAction(namespace).reason" placeholder="audit reason" />
                </label>
                <button class="artifact-action" type="submit" :disabled="loading">Update</button>
              </form>
            </div>
          </div>
        </article>

        <article class="panel full-width-panel">
          <h2>Publisher Moderation</h2>
          <p class="tooling-note">Suspend compromised or abusive publishers, reactivate cleared publishers, or adjust trust level after review.</p>
          <p v-if="publishers.length === 0" class="empty-state">No publishers found.</p>
          <div v-else class="admin-table">
            <div v-for="publisher in publishers" :key="publisher.publisher_id" class="admin-row">
              <div>
                <strong>{{ publisher.display_name }}</strong>
                <span><code>{{ publisher.publisher_id }}</code> · {{ publisher.status }} · {{ publisher.trust_level }}</span>
                <span>{{ publisher.website_url || 'no website declared' }}</span>
                <span>Updated {{ formatRegistryTimestamp(publisher.updated_at) }}</span>
              </div>
              <form class="admin-action-form" @submit.prevent="updatePublisher(publisher)">
                <label class="form-field">
                  <span>Status</span>
                  <select v-model="ensurePublisherAction(publisher).status">
                    <option value="active">active</option>
                    <option value="pending_review">pending_review</option>
                    <option value="suspended">suspended</option>
                  </select>
                </label>
                <label class="form-field">
                  <span>Trust</span>
                  <select v-model="ensurePublisherAction(publisher).trustLevel">
                    <option value="unverified">unverified</option>
                    <option value="verified">verified</option>
                    <option value="official">official</option>
                  </select>
                </label>
                <label class="form-field">
                  <span>Reason</span>
                  <input v-model="ensurePublisherAction(publisher).reason" placeholder="audit reason" />
                </label>
                <button class="artifact-action" type="submit" :disabled="loading">Update</button>
              </form>
            </div>
          </div>
        </article>

        <article class="panel full-width-panel">
          <h2>Artifact Ownership Moderation</h2>
          <p class="tooling-note">Suspend package or template ownership to block new versions while keeping the audit trail explicit.</p>
          <p v-if="artifacts.length === 0" class="empty-state">No package or template ownership records found.</p>
          <div v-else class="admin-table">
            <div v-for="artifact in artifacts" :key="artifactKey(artifact)" class="admin-row">
              <div>
                <strong>{{ artifact.artifact_id }}</strong>
                <span>{{ artifact.artifact_kind }} · {{ artifact.status }} · namespace {{ artifact.namespace }}</span>
                <span>Updated {{ formatRegistryTimestamp(artifact.updated_at) }}</span>
              </div>
              <form class="admin-action-form" @submit.prevent="updateArtifact(artifact)">
                <label class="form-field">
                  <span>Status</span>
                  <select v-model="ensureArtifactAction(artifact).status">
                    <option value="active">active</option>
                    <option value="suspended">suspended</option>
                    <option value="transferred">transferred</option>
                  </select>
                </label>
                <label class="form-field">
                  <span>Reason</span>
                  <input v-model="ensureArtifactAction(artifact).reason" placeholder="audit reason" />
                </label>
                <button class="artifact-action" type="submit" :disabled="loading">Update</button>
              </form>
            </div>
          </div>
        </article>
      </section>
    </template>
  </section>
</template>
