import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    'intro',
    'why-anip',
    'anip-for-everyone',
    'anip-for-developers',
    'feature-map',
    {
      type: 'category',
      label: 'Concepts',
      items: [
        'concepts/architecture',
        'concepts/ecosystem',
        'concepts/anip-vs-mcp',
        'concepts/lifecycle-and-revisions',
        'concepts/scenario-driven-execution',
        'concepts/execution-scenario-validation',
      ],
    },
    {
      type: 'category',
      label: 'Getting Started',
      items: [
        'getting-started/first-10-minutes',
        'getting-started/install',
        'getting-started/quickstart',
        'getting-started/studio',
        'getting-started/registry',
        'getting-started/local-platform',
        'getting-started/configuration',
        'getting-started/observability',
        'getting-started/scaling',
        'getting-started/showcases',
        'getting-started/generate-service',
        'getting-started/package-trust-loop',
      ],
    },
    {
      type: 'category',
      label: 'Studio',
      items: [
        'studio/overview',
        'studio/pm-business',
        'studio/developers',
        'studio/project-types',
        'studio/page-by-page',
        'studio/ai-assistant-modes',
        'studio/templates',
        'studio/package-publishing',
        'studio/fronting',
      ],
    },
    {
      type: 'category',
      label: 'Protocol',
      items: [
        'protocol/reference',
        'protocol/capabilities',
        'protocol/authentication',
        'protocol/delegation-permissions',
        'protocol/lineage',
        'protocol/failures-cost-audit',
        'protocol/checkpoints-trust',
      ],
    },
    {
      type: 'category',
      label: 'Transports',
      items: [
        'transports/overview',
        'transports/http',
        'transports/stdio',
        'transports/grpc',
      ],
    },
    {
      type: 'category',
      label: 'Implementation',
      items: [
        'patterns/fronting',
        'generated-services/interfaces',
        'generated-services/custom-code-bundles',
      ],
    },
    {
      type: 'category',
      label: 'Testing & Validation',
      items: [
        'testing/conformance-contract-testing',
      ],
    },
    {
      type: 'category',
      label: 'Showcases',
      items: [
        'showcases/overview',
        {
          type: 'category',
          label: 'GTM Agent',
          items: [
            'showcases/gtm-agent/overview',
            'showcases/gtm-agent/business-intent',
            'showcases/gtm-agent/architecture',
            'showcases/gtm-agent/data-bi',
            'showcases/gtm-agent/capability-map',
            'showcases/gtm-agent/agent-execution',
            'showcases/gtm-agent/questions-and-extensions',
            'showcases/gtm-agent/generated-services',
            'showcases/gtm-agent/docker-compose',
            'showcases/gtm-agent/testing',
            'showcases/gtm-agent/troubleshooting',
            'showcases/gtm-language-parity',
          ],
        },
        {
          type: 'category',
          label: 'Fronting Apps',
          items: [
            'showcases/fronting',
            'showcases/fronting-apps/validation-levels',
            'showcases/fronting-apps/jira',
            'showcases/fronting-apps/github',
            'showcases/fronting-apps/gitlab',
            'showcases/fronting-apps/slack',
            'showcases/fronting-apps/linear',
            'showcases/fronting-apps/notion',
            'showcases/fronting-apps/superset',
          ],
        },
      ],
    },
    {
      type: 'category',
      label: 'Operations',
      items: [
        'operations/deployment',
        'operations/troubleshooting',
      ],
    },
    {
      type: 'category',
      label: 'Tooling',
      items: [
        'tooling/cli',
        'tooling/registry',
        'tooling/studio',
      ],
    },
    {
      type: 'category',
      label: 'Contributing',
      items: [
        'contributing/docs-testing',
      ],
    },
    {
      type: 'category',
      label: 'Releases',
      items: [
        'releases/what-ships-today',
        'releases/version-history',
      ],
    },
  ],
};

export default sidebars;
