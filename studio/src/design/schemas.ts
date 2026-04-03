import Ajv2020 from 'ajv/dist/2020'

// Schemas copied from tooling/schemas/ into Studio source so Docker builds work
// (Docker context is studio/ only — tooling/ is outside the build context)
import requirementsSchema from './schemas/requirements.schema.json'
import proposalSchema from './schemas/proposal.schema.json'
import scenarioSchema from './schemas/scenario.schema.json'

const ajv = new Ajv2020({ allErrors: true })

export const validateRequirements = ajv.compile(requirementsSchema)
export const validateProposal = ajv.compile(proposalSchema)
export const validateScenario = ajv.compile(scenarioSchema)
