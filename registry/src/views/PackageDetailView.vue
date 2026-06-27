<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getPackage, getReceipt, packageLockURL, type RegistryPackageRecord, type RegistryReceipt } from '../api'
import { formatRegistryTimestamp, formatTimestampRef } from '../datetime'

const props = defineProps<{
  packageId: string
  version: string
}>()

const loading = ref(true)
const error = ref<string | null>(null)
const record = ref<RegistryPackageRecord | null>(null)
const receipt = ref<RegistryReceipt | null>(null)
const copiedCodeBlockId = ref<string | null>(null)
let copiedCodeTimeout: ReturnType<typeof setTimeout> | null = null

function displayReadinessText(value: unknown): string {
  return String(value ?? '')
    .replace(
      'Studio needs to know what happens when the user leaves it out.',
      'The package should state what happens when the caller omits it.',
    )
    .replace(
      'Studio needs a reviewed decision about whether the service chooses that group, or the consuming app chooses it before calling.',
      'The package should state whether the service chooses that group, or the consuming app chooses it before calling.',
    )
    .replace(
      'Studio does not know how approval should be granted and resumed.',
      'The contract does not define how approval should be granted and resumed.',
    )
    .replace(
      'Studio does not yet know what kind of business value it represents or how a user should provide it.',
      'The contract does not yet state what kind of business value it represents or how a user should provide it.',
    )
    .replace(
      'Studio does not know what each choice means in business language.',
      'The contract does not explain what each choice means in business language.',
    )
    .replace(
      'Studio needs to know whether one service owns the full flow, or the consuming app coordinates the steps.',
      'The contract should state whether one service owns the full flow, or the consuming app coordinates the steps.',
    )
}

function readinessFindingCapability(finding: Record<string, any>): string {
  return String(finding.capability_id ?? 'this capability')
}

function readinessFindingInput(finding: Record<string, any>): string {
  return String(finding.input_name ?? 'this input')
}

function readinessConsumerImpact(finding: Record<string, any>): string {
  const capability = readinessFindingCapability(finding)
  const input = readinessFindingInput(finding)
  switch (finding.category) {
    case 'declared_defaults':
      return `If the consuming app omits ${input}, the package does not declare whether ${capability} should use a default, ask for clarification, or let the service resolve the value.`
    case 'clarification_behavior':
      return `The consuming app or runtime may need to ask the user for ${input} before invoking ${capability}, because the contract does not fully describe the missing-value behavior.`
    case 'derived_target':
      return `Requests for vague targets such as top, selected, recommended, or at-risk records may need app-side selection or clarification before invoking ${capability}.`
    case 'approval_boundary':
      return `This capability may involve approval-gated behavior, but consumers should not treat approval handling as complete until the approval grant flow is explicit.`
    case 'app_glue':
      return `The consuming app may need extra routing, wording, or selection logic before invoking ${capability}.`
    case 'composition_candidate':
      return 'A multi-step request may require app-side orchestration unless the package explicitly owns the composed flow.'
    default:
      return displayReadinessText(finding.detail)
  }
}

function readinessConsumerAction(finding: Record<string, any>): string {
  const capability = readinessFindingCapability(finding)
  const input = readinessFindingInput(finding)
  switch (finding.category) {
    case 'declared_defaults':
      return `Choose one integration policy: always pass ${input}, configure a local default, or prompt the user before calling ${capability}.`
    case 'clarification_behavior':
      return `Add app-side clarification for ${input}, or confirm the generated/runtime service returns a clear clarification response.`
    case 'derived_target':
      return 'Decide whether the app selects the target before invocation or asks the user to clarify vague target requests.'
    case 'approval_boundary':
      return 'Wire this capability through a real approval grant/check before enabling write or dispatch behavior.'
    case 'app_glue':
      return 'Review the Agent App Guidance section and implement the listed app-owned behavior in the consuming app.'
    case 'composition_candidate':
      return 'Either use a composed capability that owns the flow, or orchestrate the steps explicitly in the consuming app.'
    default:
      return displayReadinessText(finding.recommendation)
  }
}

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

function formatTokenLabel(value: unknown): string {
  const text = String(value ?? '').trim()
  if (!text) return ''
  return text
    .replace(/[._-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/\b\w/g, (match) => match.toUpperCase())
}

function capabilityId(capability: Record<string, any>): string {
  return String(capability.capability_id ?? capability.id ?? 'unknown.capability')
}

function capabilityGuidance(capability: Record<string, any>): Record<string, any> | null {
  const capabilities = agentConsumability.value?.capabilities
  if (!capabilities || typeof capabilities !== 'object') return null
  const guidance = (capabilities as Record<string, unknown>)[capabilityId(capability)]
  return guidance && typeof guidance === 'object' ? guidance as Record<string, any> : null
}

function capabilityEffects(capability: Record<string, any>, key: 'produces' | 'does_not_produce'): string[] {
  const direct = capability.business_effects && typeof capability.business_effects === 'object'
    ? asStringArray((capability.business_effects as Record<string, unknown>)[key])
    : []
  const guidance = capabilityGuidance(capability)
  const guided = guidance?.business_effects && typeof guidance.business_effects === 'object'
    ? asStringArray((guidance.business_effects as Record<string, unknown>)[key])
    : []
  return Array.from(new Set([...direct, ...guided]))
}

function capabilityInputs(capability: Record<string, any>, required: boolean): Record<string, any>[] {
  return asRecordArray(capability.inputs).filter((input) => Boolean(input.required) === required)
}

function inputLabel(input: Record<string, any>): string {
  const name = String(input.input_name ?? '').trim()
  const type = String(input.input_type ?? input.semantic_type ?? '').trim()
  return type ? `${name}: ${type}` : name
}

function inputBehavior(input: Record<string, any>): string {
  const defaultValue = String(input.default_value ?? '').trim()
  if (defaultValue) return `default ${defaultValue}`
  const clarification = String(input.clarification_hint ?? '').trim()
  if (clarification) return 'clarifies when missing'
  return input.required ? 'required' : 'optional'
}

function capabilityPosture(capability: Record<string, any>): string {
  if (capability.grant_policy && typeof capability.grant_policy === 'object') return 'Approval gated'
  const terms = [
    capability.intent_type,
    capability.operation_type,
    capability.side_effect_level,
    ...capabilityEffects(capability, 'produces'),
  ].join(' ').toLowerCase()
  if (terms.includes('approval')) return 'Approval required'
  if (terms.includes('mutation') || terms.includes('write') || terms.includes('dispatch') || terms.includes('send')) {
    return 'Write-adjacent'
  }
  return 'Read / prepare'
}

function capabilityAppGuidance(capability: Record<string, any>): string {
  const guidance = capabilityGuidance(capability)
  const appGlue = String(capability.implementation_fit?.category ?? '').includes('agent_app_glue')
  const reason = String(capability.implementation_fit?.rationale ?? '').trim()
  const requiredContext = asRecordArray(guidance?.required_context)
  if (appGlue && reason) return reason
  if (appGlue) return 'Requires consuming-app guidance.'
  if (requiredContext.length) {
    const clarifyInputs = requiredContext
      .filter((item) => String(item.missing_behavior ?? '').includes('clarify'))
      .map((item) => String(item.input ?? '').trim())
      .filter(Boolean)
    if (clarifyInputs.length) return `Clarify before invocation when missing: ${clarifyInputs.join(', ')}.`
  }
  return ''
}

const manifestJson = computed(() => JSON.stringify(record.value?.manifest ?? {}, null, 2))
const definitionJson = computed(() => JSON.stringify(record.value?.service_definition ?? {}, null, 2))
const lockJson = computed(() => JSON.stringify(record.value?.recommended_lock ?? {}, null, 2))
const lockDownloadHref = computed(() => packageLockURL(props.packageId, props.version))
const capabilityRecords = computed(() => asRecordArray(record.value?.service_definition?.capability_formalizations))
const capabilityCount = computed(() => {
  return capabilityRecords.value.length
})
const serviceCount = computed(() => {
  const bindings = record.value?.service_definition?.service_topology_bindings
  return Array.isArray(bindings) ? bindings.length : 0
})
const packageName = computed(() =>
  String(record.value?.manifest?.name ?? record.value?.package_id ?? props.packageId),
)
const packageVersion = computed(() =>
  String(record.value?.manifest?.version ?? record.value?.package_version ?? props.version),
)
const schemaLabel = computed(() => record.value?.schema_version || 'Unknown schema')
const lifecycleStatus = computed(() => record.value?.lifecycle?.status || 'active')
const lifecycleIsActive = computed(() => lifecycleStatus.value === 'active')
const lifecycleReplacement = computed(() => record.value?.lifecycle?.replacement ?? null)
const lifecycleMessage = computed(() => {
  const status = lifecycleStatus.value
  if (status === 'active') return ''
  const reason = record.value?.lifecycle?.reason
  const replacement = lifecycleReplacement.value
    ? ` Use ${lifecycleReplacement.value.package_id}@${lifecycleReplacement.value.package_version} instead.`
    : ''
  const base = status === 'superseded'
    ? 'This package version has been superseded.'
    : status === 'deprecated'
      ? 'This package version is deprecated and should not be used for new generation.'
      : status === 'yanked'
        ? 'This package version has been yanked and is blocked by default generation flows.'
        : status === 'takedown'
          ? 'This package version is unavailable.'
          : `This package version is ${status}.`
  return `${base}${reason ? ` Reason: ${reason}.` : ''}${replacement}`
})
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
const productRevisionLabel = computed(() => {
  const product = record.value?.lineage?.product_revision
  if (!product) return formatTimestampRef(record.value?.product_revision_ref)
  return product.revision_number
    ? `${formatTimestampRef(product.ref ?? record.value?.product_revision_ref)} (r${product.revision_number})`
    : formatTimestampRef(product.ref ?? product.artifact_id ?? record.value?.product_revision_ref)
})
const developerRevisionLabel = computed(() => {
  const developer = record.value?.lineage?.developer_revision
  if (!developer) return formatTimestampRef(record.value?.developer_revision_ref)
  return developer.revision_number
    ? `${formatTimestampRef(developer.ref ?? record.value?.developer_revision_ref)} (r${developer.revision_number})`
    : formatTimestampRef(developer.ref ?? developer.artifact_id ?? record.value?.developer_revision_ref)
})
const agentReadiness = computed(() => {
  const manifestReadiness = record.value?.manifest?.agent_consumption_readiness
  if (manifestReadiness && typeof manifestReadiness === 'object') return manifestReadiness as Record<string, any>
  const lockReadiness = record.value?.recommended_lock?.agent_consumption_readiness
  if (lockReadiness && typeof lockReadiness === 'object') return lockReadiness as Record<string, any>
  return null
})
const agentReadinessSummary = computed(() => {
  const summary = agentReadiness.value?.summary
  return summary && typeof summary === 'object' ? summary as Record<string, any> : {}
})
const agentReadinessFindings = computed(() => {
  const findings = agentReadiness.value?.findings
  return Array.isArray(findings)
    ? findings
        .map((item) => item && typeof item === 'object' ? item as Record<string, any> : null)
        .filter((item): item is Record<string, any> => Boolean(item))
    : []
})
const agentReadinessStatus = computed(() => String(agentReadiness.value?.status ?? 'missing'))
const agentReadinessScore = computed(() => Number(agentReadiness.value?.score ?? 0))
const agentReadinessIsPerfect = computed(() => agentReadinessScore.value >= 100)
const agentConsumability = computed(() => {
  const manifestConsumability = record.value?.manifest?.agent_consumability
  if (manifestConsumability && typeof manifestConsumability === 'object') return manifestConsumability as Record<string, any>
  const lockConsumability = record.value?.recommended_lock?.agent_consumability
  if (lockConsumability && typeof lockConsumability === 'object') return lockConsumability as Record<string, any>
  return null
})
const agentConsumabilityCapabilityCount = computed(() => {
  const capabilities = agentConsumability.value?.capabilities
  if (capabilities && typeof capabilities === 'object') return Object.keys(capabilities).length
  return Number(agentConsumability.value?.capability_count ?? 0)
})
const agentSimulation = computed(() => {
  const manifestSimulation = record.value?.manifest?.agent_consumption_simulation
  if (manifestSimulation && typeof manifestSimulation === 'object') return manifestSimulation as Record<string, any>
  const lockSimulation = record.value?.recommended_lock?.agent_consumption_simulation
  if (lockSimulation && typeof lockSimulation === 'object') return lockSimulation as Record<string, any>
  return null
})
const agentSimulationGate = computed(() => {
  const gate = record.value?.manifest?.agent_consumption_publication_gate ?? record.value?.recommended_lock?.agent_consumption_publication_gate
  return gate && typeof gate === 'object' ? gate as Record<string, any> : null
})
const packageReadme = computed(() => {
  const direct = String(record.value?.readme ?? '').trim()
  if (direct) return direct
  return String(record.value?.manifest?.readme ?? '').trim()
})
type ReadmeBlock = {
  id: string
  kind: 'heading' | 'paragraph' | 'code'
  level?: number
  text: string
}

const packageReadmeBlocks = computed<ReadmeBlock[]>(() => {
  const source = packageReadme.value
  if (!source) return []

  const blocks: ReadmeBlock[] = []
  const paragraphLines: string[] = []
  let codeLines: string[] = []
  let inCode = false

  function flushParagraph() {
    const text = paragraphLines.join(' ').replace(/\s+/g, ' ').trim()
    paragraphLines.length = 0
    if (!text) return
    blocks.push({ id: `readme-${blocks.length}`, kind: 'paragraph', text })
  }

  function flushCode() {
    const text = codeLines.join('\n').trimEnd()
    codeLines = []
    if (!text) return
    blocks.push({ id: `readme-${blocks.length}`, kind: 'code', text })
  }

  for (const rawLine of source.split(/\r?\n/)) {
    const line = rawLine.trimEnd()
    if (line.trim().startsWith('```')) {
      if (inCode) {
        flushCode()
        inCode = false
      } else {
        flushParagraph()
        inCode = true
      }
      continue
    }
    if (inCode) {
      codeLines.push(line)
      continue
    }

    const heading = /^(#{1,3})\s+(.+)$/.exec(line.trim())
    if (heading) {
      flushParagraph()
      blocks.push({
        id: `readme-${blocks.length}`,
        kind: 'heading',
        level: heading[1].length,
        text: heading[2].trim(),
      })
      continue
    }

    if (!line.trim()) {
      flushParagraph()
      continue
    }
    paragraphLines.push(line.trim())
  }

  if (inCode) flushCode()
  flushParagraph()
  return blocks
})
const sourceLinks = computed(() => {
  const direct = record.value?.source_links
  if (Array.isArray(direct) && direct.length) return direct
  const manifestLinks = record.value?.manifest?.source_links
  return Array.isArray(manifestLinks)
    ? manifestLinks
        .map((item) => item && typeof item === 'object' ? item as Record<string, unknown> : null)
        .filter((item): item is Record<string, unknown> => Boolean(item))
        .map((item) => ({ title: String(item.title ?? ''), url: String(item.url ?? '') }))
        .filter((item) => item.title && item.url)
    : []
})
const implementationMaterials = computed(() => {
  const direct = record.value?.implementation_materials
  if (Array.isArray(direct) && direct.length) return direct
  const manifestMaterial = record.value?.manifest?.implementation_material
  const raw = manifestMaterial && typeof manifestMaterial === 'object'
    ? (manifestMaterial as Record<string, unknown>).custom_code_bundles
    : record.value?.manifest?.implementation_materials
  return Array.isArray(raw)
    ? raw
        .map((item) => item && typeof item === 'object' ? item as Record<string, unknown> : null)
        .filter((item): item is Record<string, unknown> => Boolean(item))
        .map((item) => ({
          title: String(item.title ?? ''),
          ref: String(item.ref ?? ''),
          bundle_tree_sha256: String(item.bundle_tree_sha256 ?? ''),
        }))
        .filter((item) => item.ref)
    : []
})
const registryApiUrl = computed(() => {
  if (typeof window === 'undefined') return 'https://registry.example.com'
  return new URL('/registry-api/v1', window.location.origin).toString()
})
const packageDownloadUrl = computed(() =>
  `${registryApiUrl.value}/packages/${encodeURIComponent(record.value?.package_id ?? props.packageId)}/${encodeURIComponent(record.value?.package_version ?? props.version)}/download`,
)
const generationOutputPath = computed(() => `./generated/${record.value?.package_id ?? props.packageId}`)
const generationLockPath = computed(() => `${generationOutputPath.value}/anip.lock.json`)
const baseGenerateCommand = computed(() =>
  `go run ./cmd/anip-generate --registry-url ${registryApiUrl.value} --package-id ${record.value?.package_id ?? props.packageId} --package-version ${record.value?.package_version ?? props.version} --target python --dependency-source registry --output ${generationOutputPath.value} --write-lock ${generationLockPath.value} --force`,
)
const firstImplementationMaterial = computed(() => implementationMaterials.value[0] ?? null)
const implementationDigest = computed(() => firstImplementationMaterial.value?.bundle_tree_sha256 ?? '')
const customBundleGenerateCommand = computed(() => {
  if (!firstImplementationMaterial.value) return ''
  const digest = implementationDigest.value || 'sha256:<bundle-tree-digest>'
  return `${baseGenerateCommand.value} --custom-code-bundle ./reviewed-custom-bundle --verify-custom-code-bundle-digest ${digest}`
})
const toolingMetadataJson = computed(() => JSON.stringify({
  agent_consumption_readiness: agentReadiness.value,
  agent_consumability: agentConsumability.value,
  agent_consumption_simulation: agentSimulation.value,
  agent_consumption_publication_gate: agentSimulationGate.value,
}, null, 2))

async function copyCodeBlock(id: string, text: string): Promise<void> {
  const value = text.trim()
  if (!value) return
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value)
  } else {
    const textarea = document.createElement('textarea')
    textarea.value = value
    textarea.setAttribute('readonly', 'true')
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    textarea.remove()
  }
  copiedCodeBlockId.value = id
  if (copiedCodeTimeout) clearTimeout(copiedCodeTimeout)
  copiedCodeTimeout = setTimeout(() => {
    copiedCodeBlockId.value = null
    copiedCodeTimeout = null
  }, 1600)
}

onMounted(async () => {
  try {
    const [packageRecord, receiptRecord] = await Promise.all([
      getPackage(props.packageId, props.version),
      getReceipt(props.packageId, props.version),
    ])
    record.value = packageRecord
    receipt.value = receiptRecord
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
      <router-link class="back-link" to="/packages">All Packages</router-link>
      <h1>{{ packageId }}@{{ version }}</h1>
    </div>

    <p v-if="loading">Loading package detail…</p>
    <p v-else-if="error" class="error">{{ error }}</p>

    <template v-else-if="record">
      <article class="hero-panel">
        <div>
          <span class="eyebrow">Remote Registry Authority</span>
          <h2>{{ packageName }} <span>{{ packageVersion }}</span></h2>
          <p>
            This Registry record is the remote immutable package authority for the selected Studio lineage.
            Generator and verifier clients can resolve it by package id and version.
          </p>
        </div>
        <div class="hero-badges">
          <span class="authority-pill remote">Remote Registry</span>
          <span :class="['authority-pill', publisherTrustClass]">
            {{ publisherLabel }} · {{ publisherTrustLabel }}
          </span>
          <span class="authority-pill neutral">{{ schemaLabel }}</span>
          <span
            v-if="!lifecycleIsActive"
            :class="['authority-pill', 'lifecycle-pill', lifecycleStatus]"
          >
            {{ lifecycleStatus }}
          </span>
          <span :class="['authority-pill', `readiness-${agentReadinessStatus}`]">
            Readiness {{ agentReadinessStatus.replace(/_/g, ' ') }}
          </span>
        </div>
      </article>

      <article
        v-if="!lifecycleIsActive"
        :class="['panel', 'lifecycle-banner', lifecycleStatus]"
      >
        <h2>Package Lifecycle Warning</h2>
        <p>{{ lifecycleMessage }}</p>
        <router-link
          v-if="lifecycleReplacement"
          class="artifact-action"
          :to="{ name: 'package-detail', params: { packageId: lifecycleReplacement.package_id, version: lifecycleReplacement.package_version } }"
        >
          Open replacement {{ lifecycleReplacement.package_id }}@{{ lifecycleReplacement.package_version }}
        </router-link>
      </article>

      <div class="metric-grid">
        <div class="metric-card">
          <span>Services</span>
          <strong>{{ serviceCount }}</strong>
        </div>
        <div class="metric-card">
          <span>Capabilities</span>
          <strong>{{ capabilityCount }}</strong>
        </div>
        <div class="metric-card">
          <span>Agent Readiness Score</span>
          <strong>{{ agentReadiness ? `${agentReadinessScore}/100` : '—' }}</strong>
        </div>
        <div class="metric-card">
          <span>Capability Guidance</span>
          <strong>{{ agentConsumability ? agentConsumabilityCapabilityCount : '—' }}</strong>
        </div>
        <div class="metric-card">
          <span>Required App Glue</span>
          <strong>{{ agentReadiness ? (agentReadinessSummary.required_app_glue ?? 0) : '—' }}</strong>
        </div>
        <div class="metric-card">
          <span>Downloads</span>
          <strong>{{ record.download_count ?? 0 }}</strong>
        </div>
        <div class="metric-card wide">
          <span>Contract Signature</span>
          <code>{{ record.contract_signature }}</code>
        </div>
      </div>

      <details v-if="capabilityRecords.length" class="panel capabilities-panel">
        <summary class="capabilities-summary">
          <span>
            <strong>Capabilities</strong>
            <small>Human-readable contract surface exposed by this package.</small>
          </span>
          <b>{{ capabilityRecords.length }} total</b>
        </summary>
        <p>
          Use this before opening the raw JSON. Each row summarizes what a capability does, what it needs, and what app-side behavior may be required.
        </p>
        <div class="capability-list">
          <details
            v-for="capability in capabilityRecords"
            :key="capabilityId(capability)"
            class="capability-card"
          >
            <summary>
              <span>
                <strong>{{ capability.title || capabilityId(capability) }}</strong>
                <code>{{ capabilityId(capability) }}</code>
              </span>
              <b>{{ capabilityPosture(capability) }}</b>
            </summary>
            <p v-if="capability.summary" class="capability-summary">
              {{ capability.summary }}
            </p>
            <dl class="capability-facts">
              <dt v-if="capability.service_id">Service</dt>
              <dd v-if="capability.service_id"><code>{{ capability.service_id }}</code></dd>
              <dt v-if="capability.backend_operation">Backend operation</dt>
              <dd v-if="capability.backend_operation"><code>{{ capability.backend_operation }}</code></dd>
              <dt v-if="capabilityEffects(capability, 'produces').length">Produces</dt>
              <dd v-if="capabilityEffects(capability, 'produces').length" class="chip-row">
                <span
                  v-for="effect in capabilityEffects(capability, 'produces')"
                  :key="effect"
                  class="capability-chip positive"
                >
                  {{ formatTokenLabel(effect) }}
                </span>
              </dd>
              <dt v-if="capabilityEffects(capability, 'does_not_produce').length">Does not produce</dt>
              <dd v-if="capabilityEffects(capability, 'does_not_produce').length" class="chip-row">
                <span
                  v-for="effect in capabilityEffects(capability, 'does_not_produce')"
                  :key="effect"
                  class="capability-chip negative"
                >
                  {{ formatTokenLabel(effect) }}
                </span>
              </dd>
              <dt v-if="capabilityInputs(capability, true).length">Required inputs</dt>
              <dd v-if="capabilityInputs(capability, true).length" class="chip-row">
                <span
                  v-for="input in capabilityInputs(capability, true)"
                  :key="input.input_name"
                  class="capability-chip"
                  :title="inputBehavior(input)"
                >
                  {{ inputLabel(input) }}
                </span>
              </dd>
              <dt v-if="capabilityInputs(capability, false).length">Optional inputs</dt>
              <dd v-if="capabilityInputs(capability, false).length" class="chip-row">
                <span
                  v-for="input in capabilityInputs(capability, false)"
                  :key="input.input_name"
                  class="capability-chip optional"
                  :title="inputBehavior(input)"
                >
                  {{ inputLabel(input) }}
                </span>
              </dd>
              <dt v-if="capabilityAppGuidance(capability)">App guidance</dt>
              <dd v-if="capabilityAppGuidance(capability)">
                {{ capabilityAppGuidance(capability) }}
              </dd>
            </dl>
          </details>
        </div>
      </details>

      <div class="detail-grid">
        <article class="panel package-overview-panel">
          <h2>Package Overview</h2>
          <div v-if="packageReadmeBlocks.length" class="readme-blocks">
            <template v-for="block in packageReadmeBlocks" :key="block.id">
              <h3 v-if="block.kind === 'heading' && block.level === 1" class="readme-heading primary">
                {{ block.text }}
              </h3>
              <h4 v-else-if="block.kind === 'heading'" class="readme-heading">
                {{ block.text }}
              </h4>
              <div v-else-if="block.kind === 'code'" class="code-example">
                <button
                  class="copy-code-button"
                  type="button"
                  :aria-label="copiedCodeBlockId === block.id ? 'Copied command' : 'Copy command'"
                  @click="copyCodeBlock(block.id, block.text)"
                >
                  {{ copiedCodeBlockId === block.id ? 'Copied' : 'Copy' }}
                </button>
                <pre class="readme-code">{{ block.text }}</pre>
              </div>
              <p v-else class="readme-text">{{ block.text }}</p>
            </template>
          </div>
          <div v-if="sourceLinks.length" class="resource-section">
            <strong>Source Links</strong>
            <a
              v-for="link in sourceLinks"
              :key="`${link.title}:${link.url}`"
              :href="link.url"
              target="_blank"
              rel="noreferrer"
              class="resource-link"
            >
              {{ link.title }}
            </a>
          </div>
          <div v-if="implementationMaterials.length" class="resource-section">
            <strong>Implementation Materials</strong>
            <div
              v-for="material in implementationMaterials"
              :key="material.ref"
              class="material-card"
            >
              <b>{{ material.title || 'Implementation material' }}</b>
              <code>{{ material.ref }}</code>
              <span v-if="material.bundle_tree_sha256">Tree digest: {{ material.bundle_tree_sha256 }}</span>
            </div>
          </div>
          <div class="resource-section">
            <strong>Generate Code</strong>
            <a class="resource-link download-link" :href="packageDownloadUrl">
              Download package record
            </a>
            <p class="tooling-note">
              Registry derives this command from the immutable package id and version. It writes a local lock file so later generation/validation can fail closed on digest drift.
            </p>
            <div class="code-example">
              <button
                class="copy-code-button"
                type="button"
                :aria-label="copiedCodeBlockId === 'generate-registry' ? 'Copied command' : 'Copy command'"
                @click="copyCodeBlock('generate-registry', baseGenerateCommand)"
              >
                {{ copiedCodeBlockId === 'generate-registry' ? 'Copied' : 'Copy' }}
              </button>
              <pre class="command-block">{{ baseGenerateCommand }}</pre>
            </div>
            <template v-if="customBundleGenerateCommand">
              <p class="tooling-note">
                This package declares custom implementation material. Remote bundle refs are not fetched automatically; apply reviewed local material explicitly.
              </p>
              <div class="code-example">
                <button
                  class="copy-code-button"
                  type="button"
                  :aria-label="copiedCodeBlockId === 'generate-custom-bundle' ? 'Copied command' : 'Copy command'"
                  @click="copyCodeBlock('generate-custom-bundle', customBundleGenerateCommand)"
                >
                  {{ copiedCodeBlockId === 'generate-custom-bundle' ? 'Copied' : 'Copy' }}
                </button>
                <pre class="command-block">{{ customBundleGenerateCommand }}</pre>
              </div>
            </template>
          </div>
        </article>

        <article class="panel">
          <h2>Lineage</h2>
          <dl class="kv-list">
            <dt>Project</dt>
            <dd>{{ record.project_ref }}</dd>
            <dt>Product Revision</dt>
            <dd>{{ productRevisionLabel }}</dd>
            <dt>Developer Revision</dt>
            <dd>{{ developerRevisionLabel }}</dd>
            <dt v-if="record.lineage?.product_revision?.baseline_locked_at">Baseline Locked</dt>
            <dd v-if="record.lineage?.product_revision?.baseline_locked_at">{{ formatRegistryTimestamp(record.lineage.product_revision.baseline_locked_at) }}</dd>
            <dt>Published</dt>
            <dd>{{ formatRegistryTimestamp(record.published_at) }}</dd>
          </dl>
        </article>

        <article class="panel">
          <h2>Digests</h2>
          <dl class="kv-list">
            <dt>Manifest</dt>
            <dd><code>{{ record.manifest_digest }}</code></dd>
            <dt>Service Definition</dt>
            <dd><code>{{ record.definition_digest }}</code></dd>
            <dt v-if="record.lock_digest">Recommended Lock</dt>
            <dd v-if="record.lock_digest"><code>{{ record.lock_digest }}</code></dd>
          </dl>
        </article>

        <article class="panel receipt-panel">
          <h2>Receipt</h2>
          <dl class="kv-list">
            <dt>ID</dt>
            <dd>{{ receipt?.receipt_id }}</dd>
            <dt>Issued</dt>
            <dd>{{ formatRegistryTimestamp(receipt?.issued_at) }}</dd>
            <dt>Algorithm</dt>
            <dd>{{ receipt?.signature_algorithm || 'Unknown' }}</dd>
            <dt>Key ID</dt>
            <dd>{{ receipt?.key_id || 'Unknown' }}</dd>
            <dt>Registry Signature</dt>
            <dd><code>{{ receipt?.registry_signature }}</code></dd>
          </dl>
        </article>

        <article
          v-if="agentReadinessFindings.length"
          class="panel readiness-panel full-width-panel"
        >
          <h2>{{ agentReadinessIsPerfect ? 'Reviewed Readiness Notes' : 'Why Not 100/100?' }}</h2>
          <p>
            {{
              agentReadinessIsPerfect
                ? 'These findings were reviewed and accepted, so they remain visible as consumer guidance without reducing the readiness score.'
                : 'These reviewed readiness findings explain what kept the agent readiness score below perfect.'
            }}
          </p>
          <div class="readiness-list">
            <div
              v-for="finding in agentReadinessFindings"
              :key="String(finding.id ?? `${finding.capability_id}:${finding.input_name}:${finding.title}`)"
              class="readiness-card"
            >
              <div class="artifact-header">
                <strong>{{ finding.title || 'Readiness finding' }}</strong>
                <span>{{ finding.severity || 'info' }}</span>
              </div>
              <span v-if="finding.capability_id">
                Capability: <code>{{ finding.capability_id }}</code>
              </span>
              <span v-if="finding.input_name">
                Input: <code>{{ finding.input_name }}</code>
              </span>
              <span><strong>Consumer impact:</strong> {{ readinessConsumerImpact(finding) }}</span>
              <span><strong>What to do:</strong> {{ readinessConsumerAction(finding) }}</span>
            </div>
          </div>
        </article>

        <article
          v-if="agentReadiness || agentConsumability || agentSimulation || agentSimulationGate"
          class="panel readiness-panel full-width-panel"
        >
          <h2>Agent App Guidance</h2>
          <dl v-if="agentReadiness" class="kv-list">
            <dt>Status</dt>
            <dd>{{ agentReadinessStatus.replace(/_/g, ' ') }}</dd>
            <dt>Score</dt>
            <dd>{{ agentReadinessScore }}/100</dd>
            <dt>Blockers</dt>
            <dd>{{ agentReadinessSummary.blockers ?? 0 }}</dd>
            <dt>Warnings</dt>
            <dd>{{ agentReadinessSummary.warnings ?? 0 }}</dd>
            <dt>Required App Glue</dt>
            <dd>{{ agentReadinessSummary.required_app_glue ?? 0 }}</dd>
            <dt v-if="agentConsumability">Capability Guidance</dt>
            <dd v-if="agentConsumability">{{ agentConsumabilityCapabilityCount }}</dd>
          </dl>
          <p v-else>
            This package does not expose agent integration metadata.
          </p>
          <p class="tooling-note">
            Advanced metadata for generators, verifiers, and consuming app builders.
          </p>
          <details class="tooling-details">
            <summary>Show advanced integration metadata</summary>
            <pre>{{ toolingMetadataJson }}</pre>
          </details>
        </article>
      </div>

      <div class="artifact-grid">
        <article class="panel artifact-panel">
          <div class="artifact-header">
            <h2>Manifest</h2>
            <span>{{ Object.keys(record.manifest ?? {}).length }} keys</span>
          </div>
          <details class="tooling-details">
            <summary>Show manifest JSON</summary>
            <pre>{{ manifestJson }}</pre>
          </details>
        </article>

        <article class="panel artifact-panel">
          <div class="artifact-header">
            <h2>Service Definition</h2>
            <span>{{ schemaLabel }}</span>
          </div>
          <details class="tooling-details">
            <summary>Show service definition JSON</summary>
            <pre>{{ definitionJson }}</pre>
          </details>
        </article>

        <article class="panel artifact-panel">
          <div class="artifact-header">
            <h2>Publisher Recommended Lock</h2>
            <a class="artifact-action" :href="lockDownloadHref">Download lock</a>
          </div>
          <details class="tooling-details">
            <summary>Show publisher recommended lock JSON</summary>
            <pre>{{ lockJson }}</pre>
          </details>
        </article>
      </div>
    </template>
  </section>
</template>
