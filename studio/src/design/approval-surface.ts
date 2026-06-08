export type ApprovalSurfaceDescriptor = {
  listPath: string
  approvePathTemplate: string
  notes: string[]
}

function unwrapData(record: any, key: string): Record<string, any> {
  const data = record?.data
  if (data && typeof data === 'object' && data[key] && typeof data[key] === 'object') return data[key]
  if (record && typeof record === 'object' && record[key] && typeof record[key] === 'object') return record[key]
  return {}
}

export function approvalSurfaceFromArtifacts(proposal: any, shape: any): ApprovalSurfaceDescriptor | null {
  const proposalData = unwrapData(proposal, 'proposal')
  const shapeData = unwrapData(shape, 'shape')
  const developerTranslation = (proposalData.developer_translation ?? {}) as Record<string, any>
  const actorPolicyModel = (developerTranslation.actor_policy_model ?? shapeData.actor_policy_model ?? {}) as Record<string, any>
  const approvalSurface = (actorPolicyModel.approval_surface ?? {}) as Record<string, any>
  const listPath = String(approvalSurface.list_path || '').trim()
  const approvePathTemplate = String(approvalSurface.approve_path_template || '').trim()
  const notes = Array.isArray(approvalSurface.notes)
    ? approvalSurface.notes.map((item: unknown) => String(item).trim()).filter(Boolean)
    : []
  if (!listPath || !approvePathTemplate) return null
  return { listPath, approvePathTemplate, notes }
}

export function approvalReviewRoute(
  proposal: any,
  shape: any,
  extraQuery: Record<string, string | undefined> = {},
): { name: 'approvals'; query: Record<string, string> } | null {
  const surface = approvalSurfaceFromArtifacts(proposal, shape)
  if (!surface) return null
  const query: Record<string, string> = {
    listPath: surface.listPath,
    approvePathTemplate: surface.approvePathTemplate,
  }
  for (const [key, value] of Object.entries(extraQuery)) {
    if (value) query[key] = value
  }
  return {
    name: 'approvals',
    query,
  }
}
