<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  createMyToken,
  getMyPublisher,
  listMyArtifacts,
  listMyTokens,
  revokeMyToken,
  type CreatePublishTokenResult,
  type PublisherArtifactSummary,
  type RegistryPublisher,
  type RegistryPublishTokenSummary,
} from '../api'
import { formatRegistryTimestamp } from '../datetime'

const STORAGE_KEY = 'anip_registry_publisher_token'

const tokenInput = ref('')
const activeToken = ref('')
const loading = ref(false)
const error = ref<string | null>(null)
const createdToken = ref<CreatePublishTokenResult | null>(null)
const copied = ref(false)
const tokenManagementAllowed = ref(false)
const tokenManagementError = ref<string | null>(null)
const publisher = ref<RegistryPublisher | null>(null)
const artifacts = ref<PublisherArtifactSummary[]>([])
const tokens = ref<RegistryPublishTokenSummary[]>([])
const createForm = reactive({
  label: '',
  operations: ['publish:package'],
  namespaces: 'anip',
  packageIds: '',
  templateIds: '',
  expiresAt: '',
})

const hasActiveToken = computed(() => activeToken.value.trim() !== '')
const canManageTokens = computed(() => tokenManagementAllowed.value)
const activeArtifacts = computed(() => artifacts.value.filter((artifact) => artifact.status === 'active'))
const revokedTokens = computed(() => tokens.value.filter((token) => token.revoked_at))
const liveTokens = computed(() => tokens.value.filter((token) => !token.revoked_at))

function commaList(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function operationSelected(operation: string): boolean {
  return createForm.operations.includes(operation)
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

function toggleOperation(operation: string, event: Event): void {
  setOperation(operation, Boolean((event.target as HTMLInputElement | null)?.checked))
}

async function loadPublisherState(token: string): Promise<void> {
  loading.value = true
  error.value = null
  createdToken.value = null
  tokenManagementError.value = null
  try {
    const [publisherResult, artifactResult] = await Promise.all([
      getMyPublisher(token),
      listMyArtifacts(token),
    ])
    activeToken.value = token
    tokenInput.value = token
    publisher.value = publisherResult
    artifacts.value = artifactResult
    localStorage.setItem(STORAGE_KEY, token)
    try {
      tokens.value = await listMyTokens(token)
      tokenManagementAllowed.value = true
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
  await loadPublisherState(token)
}

function disconnect(): void {
  activeToken.value = ''
  tokenInput.value = ''
  publisher.value = null
  artifacts.value = []
  tokens.value = []
  createdToken.value = null
  error.value = null
  tokenManagementAllowed.value = false
  tokenManagementError.value = null
  localStorage.removeItem(STORAGE_KEY)
}

async function refresh(): Promise<void> {
  if (!hasActiveToken.value) return
  await loadPublisherState(activeToken.value)
}

async function createToken(): Promise<void> {
  if (!activeToken.value) return
  error.value = null
  createdToken.value = null
  try {
    const result = await createMyToken(activeToken.value, {
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
    await revokeMyToken(activeToken.value, tokenId)
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

onMounted(() => {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved) {
    tokenInput.value = saved
    void loadPublisherState(saved)
  }
})
</script>

<template>
  <section class="page">
    <div class="page-header">
      <h1>Publisher Console</h1>
      <p>Manage publisher-owned artifacts and scoped publish tokens. This console uses a bearer token locally in your browser; it does not create a Registry account session.</p>
    </div>

    <section class="hero-panel publisher-auth-panel">
      <div>
        <span class="eyebrow">Scoped Publisher Access</span>
        <h2>Connect with a publisher token</h2>
        <p>Use a token that belongs to the publisher you want to manage. Token creation and revocation require the <code>manage:tokens</code> operation.</p>
      </div>
      <div class="publisher-token-form">
        <label class="form-field">
          <span>Bearer token</span>
          <input v-model="tokenInput" type="password" autocomplete="off" placeholder="anip_pat_…" />
        </label>
        <div class="action-row">
          <button class="artifact-action" type="button" :disabled="loading" @click="connect">
            {{ loading ? 'Connecting…' : 'Connect' }}
          </button>
          <button v-if="hasActiveToken" class="artifact-action secondary" type="button" @click="disconnect">
            Disconnect
          </button>
        </div>
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
