import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    'intro',
    'why-anip',
    'feature-map',
    {
      type: 'category',
      label: 'Getting Started',
      items: [
        'getting-started/install',
        'getting-started/quickstart',
        'getting-started/studio-showcases',
      ],
    },
    {
      type: 'category',
      label: 'Protocol',
      items: [
        'protocol/capabilities',
        'protocol/delegation-permissions',
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
      label: 'Tooling',
      items: [
        'tooling/interfaces',
        'tooling/conformance-contract-testing',
        'tooling/studio',
        'tooling/showcases',
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
