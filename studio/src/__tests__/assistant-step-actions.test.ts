import { describe, expect, it } from 'vitest'
import { assistantStepActionsForText } from '../design/assistant-step-actions'

describe('assistant-step-actions', () => {
  it('does not infer actions without a project id', () => {
    expect(assistantStepActionsForText('Run the simulator afterward.', '')).toEqual([])
    expect(assistantStepActionsForText('Open verification.', null)).toEqual([])
  })

  it('maps simulator follow-up steps to simulator events', () => {
    expect(assistantStepActionsForText(
      'If any contract, metadata, app-glue, or service changes are reviewed, rerun the simulator to confirm the pass still holds.',
      'project-1',
    )).toContainEqual({
      id: 'run-simulator',
      label: 'Run simulator',
      tone: 'primary',
      event: 'run_simulator',
    })
  })

  it('maps readiness report handoff steps to handoff actions', () => {
    const actions = assistantStepActionsForText(
      'Attach this passing simulator report to the readiness or publication review as regression evidence.',
      'project-1',
    )

    expect(actions).toContainEqual({
      id: 'save-readiness-handoff',
      label: 'Save handoff artifact',
      tone: 'primary',
      event: 'save_readiness_handoff',
    })
    expect(actions).toContainEqual({
      id: 'open-publication',
      label: 'Open Publication',
      tone: 'primary',
      path: '/design/projects/project-1/developer/definition',
    })
  })

  it('maps gate next steps to concrete Studio destinations', () => {
    const actions = assistantStepActionsForText(
      'Proceed to generator, verifier, or publication gates only if non-simulator checks are also green.',
      'gtm-ai-recheck-20260429180003',
      'workspace-1',
    )

    expect(actions).toEqual([
      {
        id: 'open-generation',
        label: 'Open Generation',
        tone: 'primary',
        path: '/design/workspaces/workspace-1/projects/gtm-ai-recheck-20260429180003/developer/definition#generation-launch',
      },
      {
        id: 'open-verification',
        label: 'Open Verification',
        tone: 'primary',
        path: '/design/workspaces/workspace-1/projects/gtm-ai-recheck-20260429180003/verification',
      },
      {
        id: 'open-publication',
        label: 'Open Publication',
        tone: 'primary',
        path: '/design/workspaces/workspace-1/projects/gtm-ai-recheck-20260429180003/developer/definition',
      },
    ])
  })

  it('maps Coverage inspection steps to Coverage navigation', () => {
    expect(assistantStepActionsForText(
      'Use Developer Coverage to inspect whether there are untested scenarios despite the current all-pass result.',
      'project-1',
    )).toContainEqual({
      id: 'open-coverage',
      label: 'Open Coverage',
      tone: 'secondary',
      path: '/design/projects/project-1/developer/coverage',
    })
  })
})
