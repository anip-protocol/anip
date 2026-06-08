#!/usr/bin/env tsx

import * as fs from 'fs'
import * as path from 'path'
import { fileURLToPath } from 'url'
import { buildStarterTemplatePackageEnvelope } from '../src/design/starter-template-package'
import { normalizeStarterTemplate, validateStarterTemplate, type StarterTemplate } from '../src/design/starter-templates'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const repoRoot = path.resolve(__dirname, '..', '..')

type ShowcaseTemplateSource = {
  path: string
  industry: string
  systems: string[]
}

const defaultSources: ShowcaseTemplateSource[] = [
  source('jira-fronting-showcase', 'software_delivery', ['jira', 'atlassian']),
  source('github-fronting-showcase', 'software_delivery', ['github']),
  source('gitlab-fronting-showcase', 'software_delivery', ['gitlab']),
  source('slack-fronting-showcase', 'collaboration', ['slack']),
  source('notion-fronting-showcase', 'knowledge_management', ['notion']),
  source('linear-fronting-showcase', 'software_delivery', ['linear']),
  source('superset-fronting-showcase', 'analytics', ['superset']),
]

function source(exampleDir: string, industry: string, systems: string[]): ShowcaseTemplateSource {
  return {
    path: path.join(repoRoot, 'docs', 'examples', exampleDir, 'anip-fronting-starter.json'),
    industry,
    systems,
  }
}

function hasFlag(flag: string): boolean {
  return process.argv.includes(flag)
}

function argValue(flag: string): string | null {
  const index = process.argv.indexOf(flag)
  if (index === -1 || !process.argv[index + 1]) return null
  return process.argv[index + 1]
}

function readJSON(filePath: string): unknown {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'))
}

function writeJSON(filePath: string, value: unknown): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

function asTemplate(value: unknown, sourcePath: string): StarterTemplate {
  const template = normalizeStarterTemplate(value)
  const errors = validateStarterTemplate(template)
  if (errors.length > 0) {
    throw new Error(`${sourcePath} is not a valid starter template: ${errors.join(' ')}`)
  }
  return template as StarterTemplate
}

async function publishTemplate(registryURL: string, token: string, request: unknown): Promise<{ id: string; version: string }> {
  const base = registryURL.replace(/\/$/, '').endsWith('/registry-api/v1')
    ? registryURL.replace(/\/$/, '')
    : `${registryURL.replace(/\/$/, '')}/registry-api/v1`
  const response = await fetch(`${base}/templates`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  })
  const text = await response.text()
  if (!response.ok) {
    throw new Error(`publish template failed ${response.status}: ${text}`)
  }
  const payload = JSON.parse(text)
  return {
    id: payload.template.template_id,
    version: payload.template.template_version,
  }
}

async function main(): Promise<void> {
  const packageVersion = argValue('--package-version') ?? '0.1.0'
  const exportedAt = argValue('--exported-at') ?? '2026-05-15T00:00:00Z'
  const outputDir = path.resolve(argValue('--output-dir') ?? path.join(repoRoot, 'examples', 'showcase', 'templates', 'registry-templates'))
  const registryURL = argValue('--registry-url')
  const publish = hasFlag('--publish')
  const token = process.env.ANIP_REGISTRY_PUBLISH_TOKEN?.trim() ?? ''
  if (publish && (!registryURL || !token)) {
    throw new Error('--publish requires --registry-url and ANIP_REGISTRY_PUBLISH_TOKEN')
  }

  for (const item of defaultSources) {
    const template = asTemplate(readJSON(item.path), item.path)
    const pkg = await buildStarterTemplatePackageEnvelope({
      packageVersion,
      exportedAt,
      sourceProject: {
        id: `template-source:${template.id}`,
        name: template.title,
        project_type: template.projectType,
        domain: template.domain,
      },
      template,
      warnings: [
        'Template-suggested starter data must be reviewed before baseline locking or publication.',
        'Do not include workspace secrets or customer-private source documents in shared templates.',
      ],
    })
    pkg.manifest.industry = item.industry
    pkg.manifest.systems = item.systems

    const request = {
      template_id: template.id,
      template_version: packageVersion,
      manifest: pkg.manifest,
      template,
      package: pkg,
    }
    const filePath = path.join(outputDir, `${template.id}-${packageVersion}.anip-template.json`)
    writeJSON(filePath, request)

    if (publish && registryURL) {
      const result = await publishTemplate(registryURL, token, request)
      console.log(`published ${result.id}@${result.version}`)
    } else {
      console.log(`wrote ${filePath}`)
    }
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error)
  process.exit(1)
})
