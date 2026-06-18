<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  getRegistryAuthSession,
  githubAuthStartURL,
  listAdminArtifacts,
  listAdminNamespaces,
  listAdminPublishers,
  logoutRegistryAuthSession,
  transferAdminArtifactOwnership,
  updateAdminArtifactStatus,
  updateAdminNamespaceStatus,
  updateAdminPublisherStatus,
  type PublisherArtifactSummary,
  type RegistryBrowserSessionContext,
  type RegistryNamespaceSummary,
  type RegistryPublisher,
} from '../api'
import { formatRegistryTimestamp } from '../datetime'

const SESSION_SENTINEL = '__browser_session__'

const tokenInput = ref('')
const activeToken = ref('')
const browserSession = ref<RegistryBrowserSessionContext | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const success = ref<string | null>(null)
const namespaces = ref<RegistryNamespaceSummary[]>([])
const publishers = ref<RegistryPublisher[]>([])
const artifacts = ref<PublisherArtifactSummary[]>([])

const namespaceActions = reactive<Record<string, { status: string; reason: string }>>({})
const publisherActions = reactive<Record<string, { status: string; trustLevel: string; reason: string }>>({})
const artifactActions = reactive<Record<string, { status: string; reason: string }>>({})
const artifactTransferActions = reactive<Record<string, { targetPublisherId: string; targetNamespace: string; reason: string }>>({})

const hasActiveToken = computed(() => activeToken.value.trim() !== '')
const usingBrowserSession = computed(() => activeToken.value === SESSION_SENTINEL)
const activeCredential = computed(() => (usingBrowserSession.value ? null : activeToken.value))
const signedInButNotAdmin = computed(() => Boolean(browserSession.value?.user && !browserSession.value.admin && !hasActiveToken.value))
const pendingNamespaces = computed(() => namespaces.value.filter((namespace) => namespace.status === 'pending_verification'))
const suspendedPublishers = computed(() => publishers.value.filter((publisher) => publisher.status === 'suspended'))
const suspendedArtifacts = computed(() => artifacts.value.filter((artifact) => artifact.status === 'suspended'))
const activePublishers = computed(() => publishers.value.filter((publisher) => publisher.status === 'active'))
const activeNamespaces = computed(() => namespaces.value.filter((namespace) => namespace.status === 'active'))

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

function ensureArtifactTransferAction(artifact: PublisherArtifactSummary): { targetPublisherId: string; targetNamespace: string; reason: string } {
  const key = artifactKey(artifact)
  if (!artifactTransferActions[key]) {
    artifactTransferActions[key] = {
      targetPublisherId: '',
      targetNamespace: '',
      reason: '',
    }
  }
  return artifactTransferActions[key]
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
    ensureArtifactTransferAction(artifact)
  })
}

async function loadAdminState(token: string | null, source: 'token' | 'session'): Promise<void> {
  loading.value = true
  error.value = null
  success.value = null
  try {
    const [namespaceResult, publisherResult, artifactResult] = await Promise.all([
      listAdminNamespaces(token),
      listAdminPublishers(token),
      listAdminArtifacts(token),
    ])
    activeToken.value = source === 'session' ? SESSION_SENTINEL : token || ''
    if (source === 'token') {
      tokenInput.value = token || ''
    }
    namespaces.value = namespaceResult
    publishers.value = publisherResult
    artifacts.value = artifactResult
    syncActionDefaults()
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
  browserSession.value = null
  await loadAdminState(token, 'token')
}

async function disconnect(): Promise<void> {
  if (usingBrowserSession.value) {
    await logoutRegistryAuthSession().catch(() => undefined)
  }
  activeToken.value = ''
  tokenInput.value = ''
  browserSession.value = null
  namespaces.value = []
  publishers.value = []
  artifacts.value = []
  error.value = null
  success.value = null
}

async function refresh(): Promise<void> {
  if (!hasActiveToken.value) return
  await loadAdminState(activeCredential.value, usingBrowserSession.value ? 'session' : 'token')
}

async function updateNamespace(namespace: RegistryNamespaceSummary): Promise<void> {
  if (!activeToken.value) return
  error.value = null
  success.value = null
  const action = ensureNamespaceAction(namespace)
  try {
    await updateAdminNamespaceStatus(activeCredential.value, namespace.namespace, {
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
    await updateAdminPublisherStatus(activeCredential.value, publisher.publisher_id, {
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
    await updateAdminArtifactStatus(activeCredential.value, artifact.artifact_kind, artifact.artifact_id, {
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

async function transferArtifact(artifact: PublisherArtifactSummary): Promise<void> {
  if (!activeToken.value) return
  error.value = null
  success.value = null
  const action = ensureArtifactTransferAction(artifact)
  try {
    await transferAdminArtifactOwnership(activeCredential.value, artifact.artifact_kind, artifact.artifact_id, {
      target_publisher_id: action.targetPublisherId.trim(),
      target_namespace: action.targetNamespace.trim(),
      reason: action.reason.trim() || undefined,
    })
    action.targetPublisherId = ''
    action.targetNamespace = ''
    action.reason = ''
    success.value = `${artifact.artifact_kind} ${artifact.artifact_id} transferred.`
    await refresh()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

onMounted(async () => {
  browserSession.value = await getRegistryAuthSession()
  if (browserSession.value?.admin) {
    await loadAdminState(null, 'session')
  }
})
</script>

<template>
  <section class="page">
    <div class="page-header">
      <h1>Registry Admin</h1>
      <p>Moderate namespace verification, publisher status, and package or template ownership. GitHub admin sessions are the primary browser path; bearer tokens are only a bootstrap fallback.</p>
    </div>

    <section class="hero-panel publisher-auth-panel">
      <div>
        <span class="eyebrow">Admin Moderation</span>
        <h2>Sign in with GitHub</h2>
        <p>Admin access requires the signed-in GitHub login to be listed in <code>ANIP_REGISTRY_ADMIN_GITHUB_LOGINS</code>.</p>
      </div>
      <div class="publisher-token-form">
        <a class="artifact-action github-login-link" :href="githubAuthStartURL()">Sign in with GitHub</a>
        <p v-if="browserSession?.user" class="tooling-note">
          Signed in as {{ browserSession.user.display_name }}
          <template v-if="browserSession.user.github_login">(@{{ browserSession.user.github_login }})</template>
        </p>
        <p v-if="signedInButNotAdmin" class="warning-note">This GitHub account is signed in but is not configured as a Registry admin.</p>
        <button v-if="hasActiveToken" class="artifact-action secondary" type="button" :disabled="loading" @click="refresh">
          Refresh
        </button>
        <button v-if="hasActiveToken" class="artifact-action secondary" type="button" @click="disconnect">
          {{ usingBrowserSession ? 'Sign out' : 'Disconnect' }}
        </button>
        <details class="advanced-auth-panel">
          <summary>Advanced: connect with bootstrap admin token</summary>
          <p class="tooling-note">Use this only for initial setup or emergency recovery. Tokens are not stored by the browser UI.</p>
          <label class="form-field">
            <span>Admin bearer token</span>
            <input v-model="tokenInput" type="password" autocomplete="off" placeholder="admin token" :disabled="usingBrowserSession" />
          </label>
          <div class="action-row">
            <button class="artifact-action" type="button" :disabled="loading || usingBrowserSession" @click="connect">
              {{ loading ? 'Connecting…' : 'Connect token' }}
            </button>
          </div>
        </details>
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
          <p class="tooling-note">Suspend package or template ownership to block new versions, or transfer current ownership to another active publisher namespace while keeping the audit trail explicit.</p>
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
              <form class="admin-action-form transfer-form" @submit.prevent="transferArtifact(artifact)">
                <label class="form-field">
                  <span>Transfer to publisher</span>
                  <select v-model="ensureArtifactTransferAction(artifact).targetPublisherId" required>
                    <option value="" disabled>Select publisher</option>
                    <option
                      v-for="publisher in activePublishers"
                      :key="publisher.publisher_id"
                      :value="publisher.publisher_id"
                    >
                      {{ publisher.publisher_id }} · {{ publisher.trust_level }}
                    </option>
                  </select>
                </label>
                <label class="form-field">
                  <span>Target namespace</span>
                  <select v-model="ensureArtifactTransferAction(artifact).targetNamespace" required>
                    <option value="" disabled>Select namespace</option>
                    <option
                      v-for="namespace in activeNamespaces"
                      :key="namespace.namespace"
                      :value="namespace.namespace"
                    >
                      {{ namespace.namespace }} · {{ namespace.publisher_id }} · {{ namespace.artifact_kinds.join(', ') }}
                    </option>
                  </select>
                </label>
                <label class="form-field">
                  <span>Transfer reason</span>
                  <input v-model="ensureArtifactTransferAction(artifact).reason" required placeholder="audit reason" />
                </label>
                <button class="artifact-action secondary" type="submit" :disabled="loading">Transfer</button>
              </form>
            </div>
          </div>
        </article>
      </section>
    </template>
  </section>
</template>
