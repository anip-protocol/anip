import Ajv2020 from 'ajv/dist/2020'

// Import schemas as JSON — Vite supports this natively
import requirementsSchema from '../../../tooling/schemas/requirements.schema.json'
import proposalSchema from '../../../tooling/schemas/proposal.schema.json'
import scenarioSchema from '../../../tooling/schemas/scenario.schema.json'

const ajv = new Ajv2020({ allErrors: true })

export const validateRequirements = ajv.compile(requirementsSchema)
export const validateProposal = ajv.compile(proposalSchema)
export const validateScenario = ajv.compile(scenarioSchema)
