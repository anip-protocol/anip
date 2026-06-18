<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  getRegistryAuthSession,
  githubAuthStartURL,
  listAdminArtifacts,
  listAdminNamespaces,
  listAdminPublishers,
  listAdminUsers,
  logoutRegistryAuthSession,
  transferAdminArtifactOwnership,
  updateAdminArtifactStatus,
  updateAdminNamespaceStatus,
  updateAdminPublisherStatus,
  type PublisherArtifactSummary,
  type RegistryBrowserSessionContext,
  type RegistryNamespaceSummary,
  type RegistryPublisher,
  type RegistryUser,
} from '../api'
import { formatRegistryTimestamp } from '../datetime'

type AdminSection = 'users' | 'publishers' | 'namespaces' | 'artifacts'

const SESSION_SENTINEL = '__browser_session__'

const tokenInput = ref('')
const activeToken = ref('')
const browserSession = ref<RegistryBrowserSessionContext | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const success = ref<string | null>(null)
const activeSection = ref<AdminSection>('users')
const searchQuery = ref('')
const statusFilters = reactive<Record<AdminSection, string>>({
  users: '',
  publishers: '',
  namespaces: '',
  artifacts: '',
})

const users = ref<RegistryUser[]>([])
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

const filteredUsers = computed(() =>
  users.value.filter((user) =>
    matchesStatus(user.status, statusFilters.users) &&
    matchesSearch([
      user.display_name,
      user.github_login,
      user.email,
      user.status,
      user.user_id,
    ]),
  ),
)

const filteredPublishers = computed(() =>
  publishers.value.filter((publisher) =>
    matchesStatus(publisher.status, statusFilters.publishers) &&
    matchesSearch([
      publisher.publisher_id,
      publisher.publisher_type,
      publisher.display_name,
      publisher.website_url,
      publisher.status,
      publisher.trust_level,
    ]),
  ),
)

const filteredNamespaces = computed(() =>
  namespaces.value.filter((namespace) =>
    matchesStatus(namespace.status, statusFilters.namespaces) &&
    matchesSearch([
      namespace.namespace,
      namespace.publisher_id,
      namespace.status,
      namespace.artifact_kinds.join(' '),
    ]),
  ),
)

const filteredArtifacts = computed(() =>
  artifacts.value.filter((artifact) =>
    matchesStatus(artifact.status, statusFilters.artifacts) &&
    matchesSearch([
      artifact.artifact_kind,
      artifact.artifact_id,
      artifact.namespace,
      artifact.status,
    ]),
  ),
)

function artifactKey(artifact: PublisherArtifactSummary): string {
  return `${artifact.artifact_kind}:${artifact.artifact_id}`
}

function matchesStatus(value: string, filter: string): boolean {
  return !filter || value === filter
}

function matchesSearch(values: Array<string | undefined | null>): boolean {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) {
    return true
  }
  return values.some((value) => String(value || '').toLowerCase().includes(query))
}

function sectionCount(section: AdminSection): number {
  if (section === 'users') return users.value.length
  if (section === 'publishers') return publishers.value.length
  if (section === 'namespaces') return namespaces.value.length
  return artifacts.value.length
}

function setSection(section: AdminSection): void {
  activeSection.value = section
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
    ensureNamespaceAction(namespace).status = namespace.status
  })
  publishers.value.forEach((publisher) => {
    const action = ensurePublisherAction(publisher)
    action.status = publisher.status
    action.trustLevel = publisher.trust_level
  })
  artifacts.value.forEach((artifact) => {
    ensureArtifactAction(artifact).status = artifact.status
    ensureArtifactTransferAction(artifact)
  })
}

async function loadAdminState(token: string | null, source: 'token' | 'session'): Promise<void> {
  loading.value = true
  error.value = null
  success.value = null
  try {
    const [userResult, namespaceResult, publisherResult, artifactResult] = await Promise.all([
      listAdminUsers(token),
      listAdminNamespaces(token),
      listAdminPublishers(token),
      listAdminArtifacts(token),
    ])
    activeToken.value = source === 'session' ? SESSION_SENTINEL : token || ''
    if (source === 'token') {
      tokenInput.value = token || ''
    }
    users.value = userResult
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
  users.value = []
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
      <p>Moderate users, publishers, namespace verification, and package or template ownership. GitHub admin sessions are the primary browser path; bearer tokens are only a bootstrap fallback.</p>
    </div>

    <section class="hero-panel publisher-auth-panel">
      <div>
        <span class="eyebrow">Admin Console</span>
        <h2>Sign in with GitHub</h2>
        <p>Use a GitHub account with registry admin access to review moderation queues, publisher status, namespace requests, and artifact ownership.</p>
      </div>
      <div class="publisher-token-form">
        <a class="artifact-action github-login-link" :href="githubAuthStartURL('/registry/admin')">Sign in with GitHub</a>
        <p v-if="browserSession?.user" class="tooling-note">
          Signed in as {{ browserSession.user.display_name }}
          <template v-if="browserSession.user.github_login">(@{{ browserSession.user.github_login }})</template>
        </p>
        <p v-if="signedInButNotAdmin" class="warning-note">This GitHub account is signed in, but it does not have Registry admin access.</p>
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
              {{ loading ? 'Connecting...' : 'Connect token' }}
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
          <span>Users</span>
          <strong>{{ users.length }}</strong>
        </div>
        <div class="metric-card">
          <span>Pending Namespaces</span>
          <strong>{{ pendingNamespaces.length }}</strong>
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

      <section class="panel full-width-panel">
        <div class="admin-section-tabs" role="tablist" aria-label="Registry admin sections">
          <button
            v-for="section in (['users', 'publishers', 'namespaces', 'artifacts'] as AdminSection[])"
            :key="section"
            class="admin-section-tab"
            :class="{ active: activeSection === section }"
            type="button"
            @click="setSection(section)"
          >
            {{ section }}
            <span>{{ sectionCount(section) }}</span>
          </button>
        </div>

        <div class="admin-grid-toolbar">
          <label class="form-field">
            <span>Search</span>
            <input v-model="searchQuery" placeholder="Search by id, login, namespace, status..." />
          </label>

          <label v-if="activeSection === 'users'" class="form-field compact-field">
            <span>Status</span>
            <select v-model="statusFilters.users">
              <option value="">All statuses</option>
              <option value="active">active</option>
              <option value="suspended">suspended</option>
            </select>
          </label>

          <label v-if="activeSection === 'publishers'" class="form-field compact-field">
            <span>Status</span>
            <select v-model="statusFilters.publishers">
              <option value="">All statuses</option>
              <option value="active">active</option>
              <option value="pending_review">pending_review</option>
              <option value="suspended">suspended</option>
            </select>
          </label>

          <label v-if="activeSection === 'namespaces'" class="form-field compact-field">
            <span>Status</span>
            <select v-model="statusFilters.namespaces">
              <option value="">All statuses</option>
              <option value="pending_verification">pending_verification</option>
              <option value="active">active</option>
              <option value="reserved">reserved</option>
              <option value="suspended">suspended</option>
              <option value="rejected">rejected</option>
            </select>
          </label>

          <label v-if="activeSection === 'artifacts'" class="form-field compact-field">
            <span>Status</span>
            <select v-model="statusFilters.artifacts">
              <option value="">All statuses</option>
              <option value="active">active</option>
              <option value="suspended">suspended</option>
              <option value="transferred">transferred</option>
            </select>
          </label>
        </div>

        <div v-if="activeSection === 'users'" class="admin-grid-scroll">
          <table class="admin-data-table">
            <thead>
              <tr>
                <th>User</th>
                <th>GitHub</th>
                <th>Email</th>
                <th>Status</th>
                <th>Last login</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in filteredUsers" :key="user.user_id">
                <td>
                  <strong>{{ user.display_name }}</strong>
                  <span><code>{{ user.user_id }}</code></span>
                </td>
                <td>{{ user.github_login ? `@${user.github_login}` : 'not linked' }}</td>
                <td>{{ user.email || 'not shared' }}</td>
                <td><span class="status-pill">{{ user.status }}</span></td>
                <td>{{ user.last_login_at ? formatRegistryTimestamp(user.last_login_at) : 'never' }}</td>
                <td>{{ formatRegistryTimestamp(user.created_at) }}</td>
              </tr>
            </tbody>
          </table>
          <p v-if="filteredUsers.length === 0" class="empty-state">No users match the current filters.</p>
        </div>

        <div v-if="activeSection === 'publishers'" class="admin-grid-scroll">
          <table class="admin-data-table admin-action-table">
            <thead>
              <tr>
                <th>Publisher</th>
                <th>Type</th>
                <th>Status</th>
                <th>Trust</th>
                <th>Website</th>
                <th>Updated</th>
                <th>Moderation</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="publisher in filteredPublishers" :key="publisher.publisher_id">
                <td>
                  <strong>{{ publisher.display_name }}</strong>
                  <span><code>{{ publisher.publisher_id }}</code></span>
                </td>
                <td>{{ publisher.publisher_type }}</td>
                <td><span class="status-pill">{{ publisher.status }}</span></td>
                <td>{{ publisher.trust_level }}</td>
                <td>{{ publisher.website_url || 'not declared' }}</td>
                <td>{{ formatRegistryTimestamp(publisher.updated_at) }}</td>
                <td>
                  <form class="admin-inline-form" @submit.prevent="updatePublisher(publisher)">
                    <select v-model="ensurePublisherAction(publisher).status">
                      <option value="active">active</option>
                      <option value="pending_review">pending_review</option>
                      <option value="suspended">suspended</option>
                    </select>
                    <select v-model="ensurePublisherAction(publisher).trustLevel">
                      <option value="unverified">unverified</option>
                      <option value="verified">verified</option>
                      <option value="official">official</option>
                    </select>
                    <input v-model="ensurePublisherAction(publisher).reason" placeholder="audit reason" />
                    <button class="artifact-action" type="submit" :disabled="loading">Update</button>
                  </form>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="filteredPublishers.length === 0" class="empty-state">No publishers match the current filters.</p>
        </div>

        <div v-if="activeSection === 'namespaces'" class="admin-grid-scroll">
          <table class="admin-data-table admin-action-table">
            <thead>
              <tr>
                <th>Namespace</th>
                <th>Publisher</th>
                <th>Status</th>
                <th>Kinds</th>
                <th>Updated</th>
                <th>Moderation</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="namespace in filteredNamespaces" :key="namespace.namespace">
                <td><strong>{{ namespace.namespace }}</strong></td>
                <td><code>{{ namespace.publisher_id }}</code></td>
                <td><span class="status-pill">{{ namespace.status }}</span></td>
                <td>{{ namespace.artifact_kinds.join(', ') }}</td>
                <td>{{ formatRegistryTimestamp(namespace.updated_at) }}</td>
                <td>
                  <form class="admin-inline-form" @submit.prevent="updateNamespace(namespace)">
                    <select v-model="ensureNamespaceAction(namespace).status">
                      <option value="pending_verification">pending_verification</option>
                      <option value="active">active</option>
                      <option value="reserved">reserved</option>
                      <option value="suspended">suspended</option>
                      <option value="rejected">rejected</option>
                    </select>
                    <input v-model="ensureNamespaceAction(namespace).reason" placeholder="audit reason" />
                    <button class="artifact-action" type="submit" :disabled="loading">Update</button>
                  </form>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="filteredNamespaces.length === 0" class="empty-state">No namespaces match the current filters.</p>
        </div>

        <div v-if="activeSection === 'artifacts'" class="admin-grid-scroll">
          <table class="admin-data-table admin-action-table">
            <thead>
              <tr>
                <th>Artifact</th>
                <th>Kind</th>
                <th>Namespace</th>
                <th>Status</th>
                <th>Updated</th>
                <th>Moderation</th>
                <th>Transfer</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="artifact in filteredArtifacts" :key="artifactKey(artifact)">
                <td><strong>{{ artifact.artifact_id }}</strong></td>
                <td>{{ artifact.artifact_kind }}</td>
                <td>{{ artifact.namespace }}</td>
                <td><span class="status-pill">{{ artifact.status }}</span></td>
                <td>{{ formatRegistryTimestamp(artifact.updated_at) }}</td>
                <td>
                  <form class="admin-inline-form" @submit.prevent="updateArtifact(artifact)">
                    <select v-model="ensureArtifactAction(artifact).status">
                      <option value="active">active</option>
                      <option value="suspended">suspended</option>
                      <option value="transferred">transferred</option>
                    </select>
                    <input v-model="ensureArtifactAction(artifact).reason" placeholder="audit reason" />
                    <button class="artifact-action" type="submit" :disabled="loading">Update</button>
                  </form>
                </td>
                <td>
                  <form class="admin-inline-form transfer-form" @submit.prevent="transferArtifact(artifact)">
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
                    <select v-model="ensureArtifactTransferAction(artifact).targetNamespace" required>
                      <option value="" disabled>Select namespace</option>
                      <option
                        v-for="namespace in activeNamespaces"
                        :key="namespace.namespace"
                        :value="namespace.namespace"
                      >
                        {{ namespace.namespace }} · {{ namespace.publisher_id }}
                      </option>
                    </select>
                    <input v-model="ensureArtifactTransferAction(artifact).reason" required placeholder="audit reason" />
                    <button class="artifact-action secondary" type="submit" :disabled="loading">Transfer</button>
                  </form>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="filteredArtifacts.length === 0" class="empty-state">No artifact ownership records match the current filters.</p>
        </div>
      </section>
    </template>
  </section>
</template>
