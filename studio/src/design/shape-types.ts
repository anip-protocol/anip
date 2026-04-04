// TypeScript types for shape artifacts — services, concepts, coordination, derived expectations.

export interface ShapeService {
  id: string
  name: string
  role: string
  responsibilities?: string[]
  capabilities?: string[]
  owns_concepts?: string[]
}

export interface CoordinationEdge {
  from: string
  to: string
  relationship: 'handoff' | 'verification' | 'async_followup'
  description?: string
}

export interface DomainConcept {
  id: string
  name: string
  meaning: string
  owner?: string
  sensitivity?: 'none' | 'medium' | 'high'
  risk_note?: string
}

export interface ShapeData {
  id: string
  name: string
  type: 'single_service' | 'multi_service'
  notes?: string[]
  services: ShapeService[]
  coordination?: CoordinationEdge[]
  domain_concepts?: DomainConcept[]
}

export interface DerivedExpectation {
  surface: string
  reason: string
}
