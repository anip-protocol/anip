<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { getStudioSettings, updateStudioSettings } from '../project-api'
import type { AssistantRuntimeConfig, DesktopStorageStatus, RegistryTrustPolicyConfig, SimulatorRuntimeConfig } from '../project-types'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  close: []
  saved: []
}>()

const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const config = ref<AssistantRuntimeConfig | null>(null)
const simulatorConfig = ref<SimulatorRuntimeConfig | null>(null)
const registryConfig = ref<RegistryTrustPolicyConfig | null>(null)
const desktopStorage = ref<DesktopStorageStatus | null>(null)
const provider = ref('deterministic')
const model = ref('')
const baseUrl = ref('')
const apiKey = ref('')
const clearStoredKey = ref(false)
const temperature = ref('0.2')
const timeoutSeconds = ref('20')
const simulatorProvider = ref('openai')
const simulatorModel = ref('gpt-5.4-mini')
const simulatorBaseUrl = ref('')
const simulatorApiKey = ref('')
const clearSimulatorStoredKey = ref(false)
const simulatorTemperature = ref('0')
const simulatorTimeoutSeconds = ref('60')
const registryUrl = ref('')
const requiredRegistryMode = ref('')
const trustedRegistryKeyID = ref('')
const registryPublishToken = ref('')
const clearRegistryPublishToken = ref(false)

const PROVIDER_OPTIONS = [
  { value: 'deterministic', label: 'Deterministic' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'ollama', label: 'Ollama / OpenAI-compatible' },
]

watch(
  () => props.open,
  async (open) => {
    if (!open) return
    await loadConfig()
  },
  { immediate: false },
)

const readOnlyMode = computed(() => !!config.value?.read_only_mode)
const fieldLocked = (source: string | undefined) => source === 'env' || readOnlyMode.value
const apiKeyEditable = computed(() => !fieldLocked(config.value?.api_key_source))
const modelIsUsed = computed(() => !['', 'deterministic', 'none', 'off'].includes(provider.value))
const simulatorModelIsUsed = computed(() => !['', 'deterministic', 'none', 'off'].includes(simulatorProvider.value))
const modelSourceLabel = computed(() => {
  if (!modelIsUsed.value) return 'Not used'
  if (!model.value.trim()) return 'Not set'
  return sourceLabel(config.value?.model_source)
})
const simulatorModelSourceLabel = computed(() => {
  if (!simulatorModelIsUsed.value) return 'Not used'
  if (!simulatorModel.value.trim()) return 'Not set'
  return sourceLabel(simulatorConfig.value?.model_source)
})
const modelPlaceholder = computed(() => {
  if (!modelIsUsed.value) return 'Model is not used in deterministic mode'
  if (provider.value === 'openai') return 'Required, for example: gpt-5.4-mini'
  if (provider.value === 'anthropic') return 'Required, for example: claude-sonnet-4-5'
  if (provider.value === 'ollama') return 'Required, for example: qwen2.5:14b'
  return 'Required model name'
})
const baseUrlPlaceholder = computed(() => {
  if (provider.value === 'ollama') return 'Required, for example: http://127.0.0.1:11434/v1'
  if (provider.value === 'openai') return 'Optional. Leave blank to use OpenAI default.'
  if (provider.value === 'anthropic') return 'Optional. Leave blank to use Anthropic default.'
  return 'Optional custom provider endpoint'
})
const baseUrlHint = computed(() => {
  if (provider.value === 'ollama') return 'Ollama and OpenAI-compatible local runtimes need a Base URL.'
  if (provider.value === 'openai' || provider.value === 'anthropic') {
    return 'Leave blank unless you use a proxy, gateway, or custom provider endpoint.'
  }
  return 'Base URL is only needed for custom model providers.'
})
const simulatorBaseUrlPlaceholder = computed(() => {
  if (simulatorProvider.value === 'ollama') return 'Required, for example: http://127.0.0.1:11434/v1'
  if (simulatorProvider.value === 'openai') return 'Optional. Leave blank to use OpenAI default.'
  if (simulatorProvider.value === 'anthropic') return 'Optional. Leave blank to use Anthropic default.'
  return 'Optional custom provider endpoint'
})
const simulatorBaseUrlHint = computed(() => {
  if (simulatorProvider.value === 'ollama') return 'Ollama and OpenAI-compatible local runtimes need a Base URL.'
  if (simulatorProvider.value === 'openai' || simulatorProvider.value === 'anthropic') {
    return 'Leave blank unless you use a proxy, gateway, or custom provider endpoint.'
  }
  return 'Base URL is only needed for custom model providers.'
})
const registryRequiredModeLabel = computed(() =>
  registryConfig.value?.required_registry_mode || 'No mode required',
)
const registryTrustedKeyLabel = computed(() =>
  registryConfig.value?.trusted_registry_key_id || 'Not pinned',
)
const registryPublishTokenLabel = computed(() => {
  if (!registryConfig.value) return 'Unknown'
  if (registryConfig.value.publish_token_configured) return 'Configured'
  return 'Not configured'
})
const registryPolicyLabel = computed(() => {
  if (!registryConfig.value) return 'Unknown'
  if (registryConfig.value.allows_development_registry) return 'Development Registry allowed'
  if (!registryConfig.value.key_pinned) return 'Production mode required, key not pinned'
  return 'Production Registry pinned'
})
const registryUrlLocked = computed(() => fieldLocked(registryConfig.value?.registry_url_source))
const registryRequiredModeLocked = computed(() =>
  fieldLocked(registryConfig.value?.required_registry_mode_source)
  || registryConfig.value?.required_registry_mode_source === 'production-default',
)
const registryTrustedKeyLocked = computed(() => fieldLocked(registryConfig.value?.trusted_registry_key_id_source))
const registryPublishTokenLocked = computed(() => fieldLocked(registryConfig.value?.publish_token_source))
const simulatorFieldLocked = (source: string | undefined) => source === 'env' || readOnlyMode.value
const simulatorApiKeyEditable = computed(() => !simulatorFieldLocked(simulatorConfig.value?.api_key_source))
const storageModeLabel = computed(() => {
  if (!desktopStorage.value) return 'Unknown'
  if (desktopStorage.value.backend === 'sqlite') return 'Local SQLite'
  if (desktopStorage.value.backend === 'postgres') return 'Postgres'
  return desktopStorage.value.backend
})
const storageLocationLabel = computed(() => {
  if (!desktopStorage.value) return 'Unknown'
  if (desktopStorage.value.backend === 'sqlite') {
    return desktopStorage.value.sqlite_path || 'Default local SQLite path'
  }
  if (desktopStorage.value.database_url_configured) return 'DATABASE_URL configured'
  return 'Configured by Studio server environment'
})
const showcasePreloadLabel = computed(() => (
  desktopStorage.value?.showcase_preload_enabled ? 'Enabled' : 'Disabled'
))

function hydrateForm(
  next: AssistantRuntimeConfig,
  registry?: RegistryTrustPolicyConfig | null,
  simulator?: SimulatorRuntimeConfig | null,
  storage?: DesktopStorageStatus | null,
) {
  config.value = next
  if (registry !== undefined) registryConfig.value = registry
  if (simulator !== undefined) simulatorConfig.value = simulator
  if (storage !== undefined) desktopStorage.value = storage
  provider.value = next.assistant_provider || 'deterministic'
  model.value = next.assistant_model || ''
  baseUrl.value = next.assistant_base_url || ''
  apiKey.value = ''
  clearStoredKey.value = false
  temperature.value = String(next.temperature ?? 0.2)
  timeoutSeconds.value = String(next.timeout_seconds ?? 20)
  simulatorProvider.value = simulator?.simulator_provider || 'openai'
  simulatorModel.value = simulator?.simulator_model || 'gpt-5.4-mini'
  simulatorBaseUrl.value = simulator?.simulator_base_url || ''
  simulatorApiKey.value = ''
  clearSimulatorStoredKey.value = false
  simulatorTemperature.value = String(simulator?.temperature ?? 0)
  simulatorTimeoutSeconds.value = String(simulator?.timeout_seconds ?? 60)
  registryUrl.value = registry?.registry_url || ''
  requiredRegistryMode.value = registry?.required_registry_mode || ''
  trustedRegistryKeyID.value = registry?.trusted_registry_key_id || ''
  registryPublishToken.value = ''
  clearRegistryPublishToken.value = false
}

async function loadConfig() {
  loading.value = true
  error.value = null
  try {
    const settings = await getStudioSettings()
    hydrateForm(settings.assistant, settings.registry, settings.simulator, settings.desktop_storage)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load Studio settings.'
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  if (!config.value || readOnlyMode.value) return
  saving.value = true
  error.value = null
  try {
    const settings = await updateStudioSettings({
      assistant: {
        assistant_provider: fieldLocked(config.value.provider_source) ? undefined : provider.value || null,
        assistant_model: fieldLocked(config.value.model_source) ? undefined : (model.value.trim() || null),
        assistant_base_url: fieldLocked(config.value.base_url_source) ? undefined : (baseUrl.value.trim() || null),
        assistant_api_key: apiKeyEditable.value && apiKey.value.trim() ? apiKey.value.trim() : undefined,
        clear_assistant_api_key: apiKeyEditable.value && clearStoredKey.value,
        temperature: fieldLocked(config.value.temperature_source) ? undefined : Number(temperature.value),
        timeout_seconds: fieldLocked(config.value.timeout_seconds_source) ? undefined : Number(timeoutSeconds.value),
      },
      simulator: simulatorConfig.value
        ? {
            simulator_provider: simulatorFieldLocked(simulatorConfig.value.provider_source) ? undefined : simulatorProvider.value || null,
            simulator_model: simulatorFieldLocked(simulatorConfig.value.model_source) ? undefined : (simulatorModel.value.trim() || null),
            simulator_base_url: simulatorFieldLocked(simulatorConfig.value.base_url_source) ? undefined : (simulatorBaseUrl.value.trim() || null),
            simulator_api_key: simulatorApiKeyEditable.value && simulatorApiKey.value.trim() ? simulatorApiKey.value.trim() : undefined,
            clear_simulator_api_key: simulatorApiKeyEditable.value && clearSimulatorStoredKey.value,
            temperature: simulatorFieldLocked(simulatorConfig.value.temperature_source) ? undefined : Number(simulatorTemperature.value),
            timeout_seconds: simulatorFieldLocked(simulatorConfig.value.timeout_seconds_source) ? undefined : Number(simulatorTimeoutSeconds.value),
          }
        : undefined,
      registry: registryConfig.value
        ? {
            registry_url: registryUrlLocked.value ? undefined : (registryUrl.value.trim() || null),
            required_registry_mode: registryRequiredModeLocked.value ? undefined : (requiredRegistryMode.value || null),
            trusted_registry_key_id: registryTrustedKeyLocked.value ? undefined : (trustedRegistryKeyID.value.trim() || null),
            registry_publish_token: registryPublishTokenLocked.value || !registryPublishToken.value.trim() ? undefined : registryPublishToken.value.trim(),
            clear_registry_publish_token: !registryPublishTokenLocked.value && clearRegistryPublishToken.value,
          }
        : undefined,
    })
    hydrateForm(settings.assistant, settings.registry, settings.simulator, settings.desktop_storage)
    emit('saved')
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to save Studio settings.'
  } finally {
    saving.value = false
  }
}

function sourceLabel(source: string | undefined) {
  if (source === 'env') return 'Env override'
  if (source === 'production-default') return 'Production default'
  if (source === 'compatibility-default') return 'Compatibility default'
  if (source === 'stored') return 'Saved in Studio'
  if (source === 'unset') return 'Unset'
  if (source === 'none') return 'Not configured'
  return 'Default'
}
</script>

<template>
  <div v-if="open" class="assistant-config-backdrop" @click.self="emit('close')">
    <div class="assistant-config-dialog">
      <div class="assistant-config-header">
        <div>
          <h2>Settings</h2>
          <p>Studio settings combine local assistant configuration with Registry trust policy. Environment values override and lock individual fields.</p>
        </div>
        <button class="assistant-config-close" type="button" @click="emit('close')">Close</button>
      </div>

      <div v-if="loading" class="assistant-config-note">Loading settings...</div>
      <div v-else-if="error" class="assistant-config-error">{{ error }}</div>
      <template v-else-if="config">
        <div v-if="readOnlyMode" class="assistant-config-note assistant-config-warning">
          Settings are locked in read-only mode.
        </div>

        <section v-if="desktopStorage" class="assistant-config-section">
          <div class="assistant-config-section-header">
            <h3>Desktop Storage</h3>
            <p>Desktop Studio uses local SQLite by default. Shared installs should use the Studio server or Docker deployment with Postgres.</p>
          </div>
          <div class="assistant-config-grid">
            <div class="settings-readonly-card">
              <span>Mode</span>
              <span class="source-chip">{{ desktopStorage.studio_mode || 'default' }}</span>
              <strong>{{ storageModeLabel }}</strong>
            </div>
            <div class="settings-readonly-card">
              <span>Database</span>
              <span class="source-chip">{{ desktopStorage.database_url_configured ? 'Env configured' : 'Default' }}</span>
              <strong class="wrap-value">{{ storageLocationLabel }}</strong>
            </div>
            <div class="settings-readonly-card">
              <span>Showcases</span>
              <span class="source-chip">{{ desktopStorage.seed_profile }}</span>
              <strong>{{ showcasePreloadLabel }}</strong>
            </div>
          </div>
          <p class="assistant-config-subtle">{{ desktopStorage.central_install_recommendation }}</p>
        </section>

        <section class="assistant-config-section">
          <div class="assistant-config-section-header">
            <h3>LLM Assistant</h3>
            <p>Configure Studio drafting and explanation calls. Deterministic mode does not call an LLM.</p>
          </div>

          <div class="assistant-config-grid">
            <label>
              <span>Provider</span>
              <span class="source-chip">{{ sourceLabel(config.provider_source) }}</span>
              <select v-model="provider" :disabled="fieldLocked(config.provider_source)">
                <option v-for="option in PROVIDER_OPTIONS" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </label>

            <label>
              <span>Model</span>
              <span class="source-chip">{{ modelSourceLabel }}</span>
              <input
                v-model="model"
                type="text"
                :placeholder="modelPlaceholder"
                :disabled="fieldLocked(config.model_source) || !modelIsUsed"
              />
              <small class="assistant-config-hint" v-if="modelIsUsed">
                OpenAI, Anthropic, and Ollama require an explicit model name. Studio does not assume one.
              </small>
              <small class="assistant-config-hint" v-else>
                Deterministic mode does not call an LLM, so no model is needed.
              </small>
            </label>

            <label>
              <span>Base URL</span>
              <span class="source-chip">{{ sourceLabel(config.base_url_source) }}</span>
              <input
                v-model="baseUrl"
                type="text"
                :placeholder="baseUrlPlaceholder"
                :disabled="fieldLocked(config.base_url_source)"
              />
              <small class="assistant-config-hint">{{ baseUrlHint }}</small>
            </label>

            <label>
              <span>Temperature</span>
              <span class="source-chip">{{ sourceLabel(config.temperature_source) }}</span>
              <input v-model="temperature" type="number" min="0" step="0.1" :disabled="fieldLocked(config.temperature_source)" />
            </label>

            <label>
              <span>Timeout Seconds</span>
              <span class="source-chip">{{ sourceLabel(config.timeout_seconds_source) }}</span>
              <input v-model="timeoutSeconds" type="number" min="1" step="1" :disabled="fieldLocked(config.timeout_seconds_source)" />
            </label>
          </div>

          <div class="assistant-config-key">
            <div class="assistant-config-key-header">
              <strong>API Key</strong>
              <span class="source-chip">{{ sourceLabel(config.api_key_source) }}</span>
            </div>
            <p class="assistant-config-subtle" v-if="config.api_key_source === 'env'">
              The active API key comes from an environment variable. Studio will use that value and the dialog will not override it.
            </p>
            <template v-else>
              <p class="assistant-config-subtle" v-if="config.stored_api_key_configured">
                A local API key is already stored. Enter a new key to replace it, or clear the stored key below.
              </p>
              <p class="assistant-config-subtle" v-else>
                No local API key is stored. You can still use environment variables instead of saving a key here.
              </p>
              <input
                v-model="apiKey"
                type="password"
                placeholder="Enter a new API key"
                :disabled="!apiKeyEditable"
              />
              <label v-if="config.stored_api_key_configured" class="checkbox-inline">
                <input v-model="clearStoredKey" type="checkbox" :disabled="!apiKeyEditable" />
                Clear stored key on save
              </label>
            </template>
          </div>
        </section>

        <section v-if="simulatorConfig" class="assistant-config-section">
          <div class="assistant-config-section-header">
            <h3>Agent Simulator</h3>
            <p>Configure the baseline model used to emulate how an ANIP-aware consuming agent will interpret package metadata before generation or deployment.</p>
          </div>

          <div class="assistant-config-grid">
            <label>
              <span>Provider</span>
              <span class="source-chip">{{ sourceLabel(simulatorConfig.provider_source) }}</span>
              <select v-model="simulatorProvider" :disabled="simulatorFieldLocked(simulatorConfig.provider_source)">
                <option v-for="option in PROVIDER_OPTIONS" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </label>

            <label>
              <span>Baseline Model</span>
              <span class="source-chip">{{ simulatorModelSourceLabel }}</span>
              <input
                v-model="simulatorModel"
                type="text"
                placeholder="gpt-5.4-mini"
                :disabled="simulatorFieldLocked(simulatorConfig.model_source) || !simulatorModelIsUsed"
              />
              <small class="assistant-config-hint">
                Use the expected low-cost consuming-agent baseline here. Studio assistant can use a stronger model separately.
              </small>
            </label>

            <label>
              <span>Base URL</span>
              <span class="source-chip">{{ sourceLabel(simulatorConfig.base_url_source) }}</span>
              <input
                v-model="simulatorBaseUrl"
                type="text"
                :placeholder="simulatorBaseUrlPlaceholder"
                :disabled="simulatorFieldLocked(simulatorConfig.base_url_source)"
              />
              <small class="assistant-config-hint">{{ simulatorBaseUrlHint }}</small>
            </label>

            <label>
              <span>Temperature</span>
              <span class="source-chip">{{ sourceLabel(simulatorConfig.temperature_source) }}</span>
              <input v-model="simulatorTemperature" type="number" min="0" step="0.1" :disabled="simulatorFieldLocked(simulatorConfig.temperature_source)" />
            </label>

            <label>
              <span>Timeout Seconds</span>
              <span class="source-chip">{{ sourceLabel(simulatorConfig.timeout_seconds_source) }}</span>
              <input v-model="simulatorTimeoutSeconds" type="number" min="1" step="1" :disabled="simulatorFieldLocked(simulatorConfig.timeout_seconds_source)" />
            </label>
          </div>

          <div class="assistant-config-key">
            <div class="assistant-config-key-header">
              <strong>Simulator API Key</strong>
              <span class="source-chip">{{ sourceLabel(simulatorConfig.api_key_source) }}</span>
            </div>
            <p class="assistant-config-subtle" v-if="simulatorConfig.api_key_source === 'env'">
              The active simulator key comes from an environment variable. Studio will use that value and the dialog will not override it.
            </p>
            <template v-else>
              <p class="assistant-config-subtle" v-if="simulatorConfig.stored_api_key_configured">
                A local simulator API key is already stored. Enter a new key to replace it, or clear the stored key below.
              </p>
              <p class="assistant-config-subtle" v-else>
                No local simulator key is stored. If the provider is OpenAI, Studio can also use OPENAI_API_KEY from the environment.
              </p>
              <input
                v-model="simulatorApiKey"
                type="password"
                placeholder="Enter a simulator API key"
                :disabled="!simulatorApiKeyEditable"
              />
              <label v-if="simulatorConfig.stored_api_key_configured" class="checkbox-inline">
                <input v-model="clearSimulatorStoredKey" type="checkbox" :disabled="!simulatorApiKeyEditable" />
                Clear stored simulator key on save
              </label>
            </template>
          </div>
        </section>

        <section v-if="registryConfig" class="assistant-config-section">
          <div class="assistant-config-section-header">
            <h3>Registry Trust</h3>
            <p>Configure the Registry endpoint and verifier trust policy. Environment values override and lock individual fields.</p>
          </div>
          <div class="assistant-config-grid">
            <div class="settings-readonly-card">
              <span>Registry URL</span>
              <span class="source-chip">{{ sourceLabel(registryConfig.registry_url_source) }}</span>
              <input
                v-model="registryUrl"
                type="text"
                placeholder="http://127.0.0.1:8200"
                :disabled="registryUrlLocked"
              />
            </div>
            <div class="settings-readonly-card">
              <span>Required Mode</span>
              <span class="source-chip">{{ sourceLabel(registryConfig.required_registry_mode_source) }}</span>
              <select v-model="requiredRegistryMode" :disabled="registryRequiredModeLocked">
                <option value="">No mode required</option>
                <option value="dev">Development</option>
                <option value="production">Production</option>
              </select>
              <small class="assistant-config-hint" v-if="registryRequiredModeLocked">
                {{ registryRequiredModeLabel }}
              </small>
            </div>
            <div class="settings-readonly-card">
              <span>Trusted Key</span>
              <span class="source-chip">{{ sourceLabel(registryConfig.trusted_registry_key_id_source) }}</span>
              <input
                v-model="trustedRegistryKeyID"
                type="text"
                placeholder="registry-prod-2026-04"
                :disabled="registryTrustedKeyLocked"
              />
              <small class="assistant-config-hint">{{ registryTrustedKeyLabel }}</small>
            </div>
            <div class="settings-readonly-card">
              <span>Publish Token</span>
              <span class="source-chip">{{ sourceLabel(registryConfig.publish_token_source) }}</span>
              <input
                v-model="registryPublishToken"
                type="password"
                placeholder="Enter Registry publish token"
                :disabled="registryPublishTokenLocked"
              />
              <small class="assistant-config-hint">{{ registryPublishTokenLabel }}</small>
              <label v-if="registryConfig.publish_token_configured && registryConfig.publish_token_source !== 'env'" class="checkbox-inline">
                <input v-model="clearRegistryPublishToken" type="checkbox" :disabled="registryPublishTokenLocked" />
                Clear stored publish token on save
              </label>
            </div>
            <div class="settings-readonly-card">
              <span>Policy</span>
              <span class="source-chip">{{ registryConfig.production_mode_detected ? 'Production Studio' : 'Studio local/default' }}</span>
              <strong>{{ registryPolicyLabel }}</strong>
            </div>
          </div>
          <div v-if="registryConfig.warning" class="assistant-config-note assistant-config-warning">
            {{ registryConfig.warning }}
          </div>
        </section>

        <div class="assistant-config-footer">
          <div class="assistant-config-status">
            <span class="status-chip" :class="{ ready: config.api_key_configured }">
              {{ config.api_key_configured ? 'LLM key configured' : 'No active LLM key' }}
            </span>
            <span v-if="simulatorConfig" class="status-chip" :class="{ ready: simulatorConfig.api_key_configured }">
              {{ simulatorConfig.api_key_configured ? 'Simulator key configured' : 'No simulator key' }}
            </span>
          </div>
          <button class="assistant-config-save" type="button" :disabled="saving || readOnlyMode" @click="handleSave">
            {{ saving ? 'Saving...' : 'Save Settings' }}
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.assistant-config-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(10, 16, 28, 0.64);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: 80;
}

.assistant-config-dialog {
  width: min(760px, 100%);
  max-height: calc(100vh - 48px);
  overflow: auto;
  background: var(--bg-panel, #151525);
  border: 1px solid var(--border);
  border-radius: 18px;
  box-shadow: 0 28px 70px rgba(0, 0, 0, 0.28);
  padding: 24px;
}

.assistant-config-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}

.assistant-config-header h2 {
  margin: 0 0 6px;
  font-size: 20px;
}

.assistant-config-section {
  margin-bottom: 22px;
}

.assistant-config-section-header {
  margin-bottom: 12px;
}

.assistant-config-section-header h3 {
  margin: 0 0 4px;
  font-size: 15px;
}

.assistant-config-section-header p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.5;
}

.assistant-config-header p,
.assistant-config-subtle,
.assistant-config-hint {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.5;
}

.assistant-config-hint {
  font-size: 12px;
}

.assistant-config-close,
.assistant-config-save {
  border: 1px solid var(--border);
  background: var(--bg-elevated, var(--bg-input, #1e1e38));
  color: var(--text-primary);
  border-radius: 10px;
  padding: 10px 14px;
  cursor: pointer;
}

.assistant-config-save {
  background: var(--accent);
  border-color: var(--accent);
  color: white;
}

.assistant-config-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}

.assistant-config-grid label,
.assistant-config-key,
.settings-readonly-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--bg-elevated, var(--bg-input, #1e1e38));
}

.assistant-config-grid input,
.assistant-config-grid select,
.assistant-config-key input,
.settings-readonly-card input,
.settings-readonly-card select {
  width: 100%;
  border: 1px solid var(--border);
  background: var(--bg-panel, #151525);
  color: var(--text-primary);
  border-radius: 10px;
  padding: 10px 12px;
}

.assistant-config-key {
  margin-bottom: 18px;
}

.settings-readonly-card strong {
  font-size: 14px;
}

.wrap-value {
  overflow-wrap: anywhere;
}

.assistant-config-key-header,
.assistant-config-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.checkbox-row,
.checkbox-inline {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
}

.checkbox-inline {
  display: flex;
  gap: 8px;
  color: var(--text-secondary);
}

.source-chip,
.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  background: rgba(148, 163, 184, 0.14);
  color: var(--text-secondary);
}

.status-chip.ready {
  background: rgba(34, 197, 94, 0.16);
  color: #15803d;
}

.assistant-config-note,
.assistant-config-error {
  padding: 12px 14px;
  border-radius: 12px;
  margin-bottom: 16px;
}

.assistant-config-note {
  background: rgba(59, 130, 246, 0.12);
  color: #1d4ed8;
}

.assistant-config-warning {
  background: rgba(245, 158, 11, 0.14);
  color: #b45309;
}

.assistant-config-error {
  background: rgba(239, 68, 68, 0.12);
  color: #b91c1c;
}

@media (max-width: 760px) {
  .assistant-config-grid {
    grid-template-columns: 1fr;
  }

  .assistant-config-key-header,
  .assistant-config-footer,
  .assistant-config-header {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
