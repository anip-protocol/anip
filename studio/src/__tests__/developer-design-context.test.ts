import { describe, expect, it } from 'vitest'

import {
  developerDesignPath,
  summarizeDeveloperDesignBlocks,
} from '../design/developer-design-context'
import type { ProjectIssueSummary } from '../design/project-issues'

function issue(severity: ProjectIssueSummary['severity'], messages: string[]): ProjectIssueSummary {
  return {
    severity,
    count: messages.length,
    messages,
  }
}

describe('developer design context summaries', () => {
  it('defaults every block to ready with canonical block navigation when no issues exist', () => {
    const summaries = summarizeDeveloperDesignBlocks({
      projectId: 'p1',
      issueIndex: {},
    })

    expect(summaries.business.status).toBe('ready')
    expect(summaries.capabilities.issueCount).toBe(0)
    expect(summaries.capabilities.issuePath).toBe(developerDesignPath('p1', 'capabilities'))
    expect(summaries.consumability.issuePath).toBe('/design/projects/p1/developer/app-glue')
  })

  it('maps warning issues to the owning block and page route', () => {
    const summaries = summarizeDeveloperDesignBlocks({
      projectId: 'p1',
      issueIndex: {
        'project-developer-data-contract-formalization': issue('warning', [
          'Data contracts need field descriptions.',
        ]),
      },
    })

    expect(summaries.capabilities.status).toBe('needs_clarification')
    expect(summaries.capabilities.issueCount).toBe(1)
    expect(summaries.capabilities.issuePath).toBe('/design/projects/p1/developer/data-contract-formalization')
    expect(summaries.capabilities.issues[0]).toContain('Data Contract Formalization: Data contracts need field descriptions.')
    expect(summaries.capabilities.sources.find((source) => source.key === 'project-developer-data-contract-formalization')).toMatchObject({
      label: 'Data Contract Formalization',
      path: '/design/projects/p1/developer/data-contract-formalization',
      status: 'needs_clarification',
      issueCount: 1,
    })
  })

  it('maps error issues to blocked status and preserves the first issue owner route', () => {
    const summaries = summarizeDeveloperDesignBlocks({
      projectId: 'p1',
      issueIndex: {
        'project-developer-capability-formalization': issue('warning', [
          'Capability summaries need review.',
        ]),
        'project-developer-data-contract-formalization': issue('error', [
          'A data contract is missing an output schema.',
        ]),
      },
    })

    expect(summaries.capabilities.status).toBe('blocked')
    expect(summaries.capabilities.issueCount).toBe(2)
    expect(summaries.capabilities.issuePath).toBe('/design/projects/p1/developer/capability-formalization')
  })

  it('adds current-page blocking state even before the shared issue index is populated', () => {
    const summaries = summarizeDeveloperDesignBlocks({
      projectId: 'p1',
      issueIndex: {},
      currentBlock: 'consumability',
      currentPageKey: 'project-developer-coverage',
      currentStatus: 'blocked',
      currentIssues: [
        'Agent Consumption Readiness is blocked (score 0/100).',
      ],
    })

    expect(summaries.consumability.status).toBe('blocked')
    expect(summaries.consumability.issueCount).toBe(1)
    expect(summaries.consumability.issues).toEqual([
      'Agent Consumption Readiness is blocked (score 0/100).',
    ])
    expect(summaries.consumability.issuePath).toBe('/design/projects/p1/developer/app-glue')
    expect(summaries.consumability.sources[0]).toMatchObject({
      current: true,
      status: 'blocked',
      issueCount: 1,
    })
  })

  it('deduplicates repeated issue messages from page status and issue index', () => {
    const message = 'High-risk confirmations need review.'
    const summaries = summarizeDeveloperDesignBlocks({
      projectId: 'p1',
      issueIndex: {
        'project-developer-coverage': issue('warning', [message]),
      },
      currentBlock: 'consumability',
      currentStatus: 'needs_clarification',
      currentIssues: [`Agent & App Glue: ${message}`],
    })

    expect(summaries.consumability.issueCount).toBe(1)
    expect(summaries.consumability.issues[0]).toBe(`Agent & App Glue: ${message}`)
  })
})
