<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  createMyToken,
  getRegistryAuthSession,
  githubAuthStartURL,
  getMyPublisherContext,
  listMyNamespaces,
  listMyArtifacts,
  listMyTokens,
  logoutRegistryAuthSession,
  createMyNamespace,
  revokeMyToken,
  updateMyPublisher,
  type CreatePublishTokenResult,
  type RegistryBrowserSessionContext,
  type PublisherArtifactSummary,
  type RegistryNamespaceSummary,
  type RegistryPublishTokenScopes,
  type RegistryPublisher,
  type RegistryPublishTokenSummary,
} from '../api'
import { formatRegistryTimestamp } from '../datetime'

const SESSION_SENTINEL = '__browser_session__'

const tokenInput = ref('')
const activeToken = ref('')
const browserSession = ref<RegistryBrowserSessionContext | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const createdToken = ref<CreatePublishTokenResult | null>(null)
const copied = ref(false)
const tokenManagementAllowed = ref(false)
const tokenManagementError = ref<string | null>(null)
const publisherManagementAllowed = ref(false)
const publisher = ref<RegistryPublisher | null>(null)
const artifacts = ref<PublisherArtifactSummary[]>([])
const namespaces = ref<RegistryNamespaceSummary[]>([])
const tokens = ref<RegistryPublishTokenSummary[]>([])
const profileForm = reactive({
  displayName: '',
  description: '',
  websiteUrl: '',
})
const namespaceForm = reactive({
  namespace: '',
  artifactKinds: ['package', 'template'],
})
const createForm = reactive({
  label: '',
  operations: ['publish:package'],
  namespaces: 'anip',
  packageIds: '',
  templateIds: '',
  expiresAt: '',
})

const hasActiveToken = computed(() => activeToken.value.trim() !== '')
const usingBrowserSession = computed(() => activeToken.value === SESSION_SENTINEL)
const activeCredential = computed(() => (usingBrowserSession.value ? null : activeToken.value))
const canManageTokens = computed(() => tokenManagementAllowed.value)
const canManagePublisher = computed(() => publisherManagementAllowed.value)
const activeArtifacts = computed(() => artifacts.value.filter((artifact) => artifact.status === 'active'))
const activeNamespaces = computed(() => namespaces.value.filter((namespace) => namespace.status === 'active'))
const revokedTokens = computed(() => tokens.value.filter((token) => token.revoked_at))
const liveTokens = computed(() => tokens.value.filter((token) => !token.revoked_at))

function hasOperation(scopes: RegistryPublishTokenScopes, operation: string): boolean {
  return scopes.operations.includes(operation)
}

function commaList(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function operationSelected(operation: string): boolean {
  return createForm.operations.includes(operation)
}

function namespaceKindSelected(kind: string): boolean {
  return namespaceForm.artifactKinds.includes(kind)
}

function setOperation(operation: string, enabled: boolean): void {
  const current = new Set(createForm.operations)
  if (enabled) {
    current.add(operation)
  } else {
    current.delete(operation)
  }
  createForm.operations = Array.from(current)
}

function setNamespaceKind(kind: string, enabled: boolean): void {
  const current = new Set(namespaceForm.artifactKinds)
  if (enabled) {
    current.add(kind)
  } else {
    current.delete(kind)
  }
  namespaceForm.artifactKinds = Array.from(current)
}

function toggleOperation(operation: string, event: Event): void {
  setOperation(operation, Boolean((event.target as HTMLInputElement | null)?.checked))
}

function toggleNamespaceKind(kind: string, event: Event): void {
  setNamespaceKind(kind, Boolean((event.target as HTMLInputElement | null)?.checked))
}

function syncProfileForm(value: RegistryPublisher): void {
  profileForm.displayName = value.display_name
  profileForm.description = value.description
  profileForm.websiteUrl = value.website_url
}

async function loadPublisherState(token: string | null, source: 'token' | 'session'): Promise<void> {
  loading.value = true
  error.value = null
  createdToken.value = null
  tokenManagementError.value = null
  try {
    const [publisherContext, artifactResult] = await Promise.all([
      getMyPublisherContext(token),
      listMyArtifacts(token),
    ])
    activeToken.value = source === 'session' ? SESSION_SENTINEL : token || ''
    if (source === 'token') {
      tokenInput.value = token || ''
    }
    publisher.value = publisherContext.publisher
    syncProfileForm(publisherContext.publisher)
    artifacts.value = artifactResult
    tokenManagementAllowed.value = hasOperation(publisherContext.scopes, 'manage:tokens')
    publisherManagementAllowed.value = hasOperation(publisherContext.scopes, 'manage:publisher')
    try {
      namespaces.value = await listMyNamespaces(token)
    } catch {
      namespaces.value = []
    }
    if (!tokenManagementAllowed.value) {
      tokens.value = []
      tokenManagementError.value = null
      return
    }
    try {
      tokens.value = await listMyTokens(token)
    } catch (err) {
      tokens.value = []
      tokenManagementAllowed.value = false
      tokenManagementError.value = err instanceof Error ? err.message : String(err)
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

async function connect(): Promise<void> {
  const token = tokenInput.value.trim()
  if (!token) {
    error.value = 'Paste a scoped publisher token first.'
    return
  }
  browserSession.value = null
  await loadPublisherState(token, 'token')
}

async function disconnect(): Promise<void> {
  if (usingBrowserSession.value) {
    await logoutRegistryAuthSession().catch(() => undefined)
  }
  activeToken.value = ''
  tokenInput.value = ''
  browserSession.value = null
  publisher.value = null
  artifacts.value = []
  namespaces.value = []
  tokens.value = []
  createdToken.value = null
  error.value = null
  tokenManagementAllowed.value = false
  publisherManagementAllowed.value = false
  tokenManagementError.value = null
}

async function refresh(): Promise<void> {
  if (!hasActiveToken.value) return
  await loadPublisherState(activeCredential.value, usingBrowserSession.value ? 'session' : 'token')
}

async function updatePublisherProfile(): Promise<void> {
  if (!activeToken.value) return
  error.value = null
  try {
    const updated = await updateMyPublisher(activeCredential.value, {
      display_name: profileForm.displayName.trim(),
      description: profileForm.description.trim(),
      website_url: profileForm.websiteUrl.trim(),
    })
    publisher.value = updated
    syncProfileForm(updated)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function createNamespace(): Promise<void> {
  if (!activeToken.value) return
  error.value = null
  try {
    await createMyNamespace(activeCredential.value, {
      namespace: namespaceForm.namespace.trim(),
      artifact_kinds: [...namespaceForm.artifactKinds],
    })
    namespaceForm.namespace = ''
    namespaces.value = await listMyNamespaces(activeCredential.value)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function createToken(): Promise<void> {
  if (!activeToken.value) return
  error.value = null
  createdToken.value = null
  try {
    const result = await createMyToken(activeCredential.value, {
      label: createForm.label.trim(),
      scopes: {
        operations: [...createForm.operations],
        namespaces: commaList(createForm.namespaces),
        package_ids: commaList(createForm.packageIds),
        template_ids: commaList(createForm.templateIds),
      },
      expires_at: createForm.expiresAt.trim() || undefined,
    })
    createdToken.value = result
    createForm.label = ''
    await refresh()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function revokeToken(tokenId: string): Promise<void> {
  if (!activeToken.value || !tokenId) return
  error.value = null
  try {
    await revokeMyToken(activeCredential.value, tokenId)
    await refresh()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function copyCreatedToken(): Promise<void> {
  if (!createdToken.value?.bearer_token) return
  await navigator.clipboard.writeText(createdToken.value.bearer_token)
  copied.value = true
  window.setTimeout(() => {
    copied.value = false
  }, 1600)
}

function scopeText(token: RegistryPublishTokenSummary): string {
  const parts = [
    token.scopes.operations.length ? `ops: ${token.scopes.operations.join(', ')}` : '',
    token.scopes.namespaces.length ? `namespaces: ${token.scopes.namespaces.join(', ')}` : '',
    token.scopes.package_ids?.length ? `packages: ${token.scopes.package_ids.join(', ')}` : '',
    token.scopes.template_ids?.length ? `templates: ${token.scopes.template_ids.join(', ')}` : '',
  ].filter(Boolean)
  return parts.join(' · ') || 'no scopes'
}

onMounted(async () => {
  browserSession.value = await getRegistryAuthSession()
  if (browserSession.value?.publisher) {
    await loadPublisherState(null, 'session')
  }
})
</script>

<template>
  <section class="page">
    <div class="page-header">
      <h1>Publisher Console</h1>
      <p>Manage publisher-owned artifacts, namespaces, and scoped publish tokens. Sign in with GitHub for browser management; use scoped tokens for CLI publishing and release automation.</p>
    </div>

    <section class="hero-panel publisher-auth-panel">
      <div>
        <span class="eyebrow">Publisher Access</span>
        <h2>{{ hasActiveToken ? 'Connected' : 'Sign in with GitHub' }}</h2>
        <p v-if="!hasActiveToken">GitHub sign-in creates or links an individual unverified publisher account for browser management. Scoped tokens remain the right path for CLI publishing and release automation.</p>
        <p v-else>Publisher console access is active for this browser session.</p>
      </div>
      <div class="publisher-token-form">
        <a v-if="!hasActiveToken" class="artifact-action github-login-link" :href="githubAuthStartURL('/registry/publisher')">Sign in with GitHub</a>
        <p v-if="browserSession?.user" class="tooling-note">
          Signed in as {{ browserSession.user.display_name }}
          <template v-if="browserSession.user.github_login">(@{{ browserSession.user.github_login }})</template>
        </p>
        <p v-else-if="hasActiveToken" class="tooling-note">Connected with a scoped publisher token.</p>
        <button v-if="hasActiveToken" class="artifact-action secondary" type="button" @click="disconnect">
          {{ usingBrowserSession ? 'Sign out' : 'Disconnect' }}
        </button>
        <details v-if="!hasActiveToken" class="advanced-auth-panel">
          <summary>Advanced: connect with a scoped publisher token</summary>
          <p class="tooling-note">Use this only for short-lived troubleshooting. Tokens are not stored by the browser UI.</p>
          <label class="form-field">
            <span>Bearer token</span>
            <input v-model="tokenInput" type="password" autocomplete="off" placeholder="anip_pat_…" :disabled="usingBrowserSession" />
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

    <template v-if="publisher">
      <section class="metric-grid">
        <div class="metric-card">
          <span>Publisher</span>
          <strong>{{ publisher.display_name }}</strong>
        </div>
        <div class="metric-card">
          <span>Trust</span>
          <strong>{{ publisher.trust_level }}</strong>
        </div>
        <div class="metric-card">
          <span>Owned Artifacts</span>
          <strong>{{ activeArtifacts.length }}</strong>
        </div>
        <div class="metric-card">
          <span>Namespaces</span>
          <strong>{{ activeNamespaces.length }}</strong>
        </div>
        <div class="metric-card">
          <span>Live Tokens</span>
          <strong>{{ liveTokens.length }}</strong>
        </div>
      </section>

      <section class="detail-grid">
        <article class="panel">
          <h2>Publisher Profile</h2>
          <dl class="kv-list">
            <dt>Publisher ID</dt>
            <dd><code>{{ publisher.publisher_id }}</code></dd>
            <dt>Type</dt>
            <dd>{{ publisher.publisher_type }}</dd>
            <dt>Status</dt>
            <dd>{{ publisher.status }}</dd>
            <dt>Website</dt>
            <dd>
              <a v-if="publisher.website_url" class="inline-link" :href="publisher.website_url" target="_blank" rel="noreferrer">{{ publisher.website_url }}</a>
              <span v-else>not declared</span>
            </dd>
          </dl>
          <p>{{ publisher.description }}</p>
          <form class="publisher-form profile-edit-form" @submit.prevent="updatePublisherProfile">
            <label class="form-field">
              <span>Display name</span>
              <input v-model="profileForm.displayName" required />
            </label>
            <label class="form-field">
              <span>Description</span>
              <input v-model="profileForm.description" />
            </label>
            <label class="form-field">
              <span>Website URL</span>
              <input v-model="profileForm.websiteUrl" />
            </label>
            <button class="artifact-action" type="submit" :disabled="!canManagePublisher">Update profile</button>
          </form>
          <p v-if="!canManagePublisher" class="warning-note">Profile and namespace changes require <code>manage:publisher</code>.</p>
        </article>

        <article class="panel">
          <h2>Create Scoped Token</h2>
          <p class="tooling-note">Create narrow tokens for release bots or local publication workflows. The token secret is shown once.</p>
          <form class="publisher-form" @submit.prevent="createToken">
            <label class="form-field">
              <span>Label</span>
              <input v-model="createForm.label" required placeholder="release bot" />
            </label>
            <fieldset class="scope-fieldset">
              <legend>Operations</legend>
              <label>
                <input type="checkbox" :checked="operationSelected('publish:package')" @change="toggleOperation('publish:package', $event)" />
                publish:package
              </label>
              <label>
                <input type="checkbox" :checked="operationSelected('publish:template')" @change="toggleOperation('publish:template', $event)" />
                publish:template
              </label>
              <label>
                <input type="checkbox" :checked="operationSelected('manage:tokens')" @change="toggleOperation('manage:tokens', $event)" />
                manage:tokens
              </label>
              <label>
                <input type="checkbox" :checked="operationSelected('manage:publisher')" @change="toggleOperation('manage:publisher', $event)" />
                manage:publisher
              </label>
            </fieldset>
            <label class="form-field">
              <span>Namespaces</span>
              <input v-model="createForm.namespaces" placeholder="anip" />
            </label>
            <label class="form-field">
              <span>Package IDs</span>
              <input v-model="createForm.packageIds" placeholder="optional exact package ids" />
            </label>
            <label class="form-field">
              <span>Template IDs</span>
              <input v-model="createForm.templateIds" placeholder="optional exact template ids" />
            </label>
            <label class="form-field">
              <span>Expires at</span>
              <input v-model="createForm.expiresAt" placeholder="optional RFC3339 timestamp" />
            </label>
            <button class="artifact-action" type="submit" :disabled="!canManageTokens">Create token</button>
          </form>
          <p v-if="!canManageTokens" class="warning-note">The connected token can inspect publisher state but does not include <code>manage:tokens</code>.</p>
          <p v-if="tokenManagementError" class="tooling-note">{{ tokenManagementError }}</p>
        </article>
      </section>

      <article v-if="createdToken" class="panel one-time-token-panel">
        <h2>New Token Secret</h2>
        <p>This bearer token is shown once. Store it now; the Registry only keeps a hash.</p>
        <code>{{ createdToken.bearer_token }}</code>
        <button class="copy-code-button" type="button" @click="copyCreatedToken">
          {{ copied ? 'Copied' : 'Copy token' }}
        </button>
      </article>

      <section class="detail-grid">
        <article class="panel full-width-panel">
          <h2>Namespaces</h2>
          <p class="tooling-note">Namespaces define where this publisher can publish package and template artifacts. Newly requested namespaces start pending verification and must be approved before publication is allowed.</p>
          <form class="publisher-form namespace-create-form" @submit.prevent="createNamespace">
            <label class="form-field">
              <span>Namespace</span>
              <input v-model="namespaceForm.namespace" required placeholder="anip-labs" />
            </label>
            <fieldset class="scope-fieldset">
              <legend>Artifact kinds</legend>
              <label>
                <input type="checkbox" :checked="namespaceKindSelected('package')" @change="toggleNamespaceKind('package', $event)" />
                package
              </label>
              <label>
                <input type="checkbox" :checked="namespaceKindSelected('template')" @change="toggleNamespaceKind('template', $event)" />
                template
              </label>
            </fieldset>
            <button class="artifact-action" type="submit" :disabled="!canManagePublisher">Create namespace</button>
          </form>
          <p v-if="namespaces.length === 0" class="empty-state">No namespaces are assigned to this publisher.</p>
          <div v-else class="resource-section">
            <div v-for="namespace in namespaces" :key="namespace.namespace" class="material-card">
              <strong>{{ namespace.namespace }}</strong>
              <span>{{ namespace.status }} · {{ namespace.artifact_kinds.join(', ') }}</span>
              <span>Updated {{ formatRegistryTimestamp(namespace.updated_at) }}</span>
            </div>
          </div>
        </article>

        <article class="panel full-width-panel">
          <h2>Owned Artifacts</h2>
          <p v-if="artifacts.length === 0" class="empty-state">No package or template ownership records for this publisher.</p>
          <div v-else class="resource-section">
            <div v-for="artifact in artifacts" :key="`${artifact.artifact_kind}:${artifact.artifact_id}`" class="material-card">
              <strong>{{ artifact.artifact_id }}</strong>
              <span>{{ artifact.artifact_kind }} · {{ artifact.status }} · namespace {{ artifact.namespace }}</span>
              <span>Updated {{ formatRegistryTimestamp(artifact.updated_at) }}</span>
            </div>
          </div>
        </article>

        <article class="panel full-width-panel">
          <h2>Publish Tokens</h2>
          <p class="tooling-note">{{ liveTokens.length }} live token{{ liveTokens.length === 1 ? '' : 's' }} · {{ revokedTokens.length }} revoked</p>
          <div class="token-table">
            <div v-for="token in tokens" :key="token.token_id" class="token-row">
              <div>
                <strong>{{ token.label }}</strong>
                <span><code>{{ token.token_id }}</code></span>
                <span>{{ scopeText(token) }}</span>
                <span>Created {{ formatRegistryTimestamp(token.created_at) }}<template v-if="token.last_used_at"> · last used {{ formatRegistryTimestamp(token.last_used_at) }}</template></span>
                <span v-if="token.revoked_at" class="danger-text">Revoked {{ formatRegistryTimestamp(token.revoked_at) }}</span>
              </div>
              <button
                class="artifact-action secondary"
                type="button"
                :disabled="Boolean(token.revoked_at) || !canManageTokens"
                @click="revokeToken(token.token_id)"
              >
                Revoke
              </button>
            </div>
          </div>
        </article>
      </section>
    </template>
  </section>
</template>
