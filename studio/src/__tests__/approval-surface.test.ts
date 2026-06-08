import { describe, expect, it } from 'vitest'
import { approvalReviewRoute, approvalSurfaceFromArtifacts } from '../design/approval-surface'

describe('approval-surface', () => {
  const proposal = {
    data: {
      proposal: {
        developer_translation: {
          actor_policy_model: {
            approval_surface: {
              list_path: '/gtm/approvals',
              approve_path_template: '/gtm/approvals/{approvalRequestId}/approve',
              notes: ['Studio can review approval state here.'],
            },
          },
        },
      },
    },
  }

  it('extracts a generic approval surface descriptor from proposal context', () => {
    expect(approvalSurfaceFromArtifacts(proposal, null)).toEqual({
      listPath: '/gtm/approvals',
      approvePathTemplate: '/gtm/approvals/{approvalRequestId}/approve',
      notes: ['Studio can review approval state here.'],
    })
  })

  it('builds an approvals route query from the generic approval surface descriptor', () => {
    expect(approvalReviewRoute(proposal, null, { status: 'pending' })).toEqual({
      name: 'approvals',
      query: {
        listPath: '/gtm/approvals',
        approvePathTemplate: '/gtm/approvals/{approvalRequestId}/approve',
        status: 'pending',
      },
    })
  })
})
