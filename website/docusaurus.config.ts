import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'ANIP',
  tagline: 'The protocol for agent-native interfaces.',
  favicon: 'img/anip-favicon.png',
  future: {
    v4: true,
  },
  url: 'https://anip.dev',
  baseUrl: '/',
  organizationName: 'anip-protocol',
  projectName: 'anip',
  onBrokenLinks: 'throw',
  headTags: [
    {
      tagName: 'meta',
      attributes: {
        name: 'algolia-site-verification',
        content: 'E586DBDFBA5FD8E7',
      },
    },
  ],
  markdown: {
    mermaid: true,
  },
  themes: ['@docusaurus/theme-mermaid'],
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },
  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl:
            'https://github.com/anip-protocol/anip/tree/main/website/',
        },
        blog: {
          showReadingTime: true,
          blogTitle: 'ANIP Blog',
          blogDescription: 'Thoughts on agent interfaces, trust, and protocol design.',
          editUrl: 'https://github.com/anip-protocol/anip/tree/main/website/',
        },
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],
  themeConfig: {
    image: 'img/anip-social-card.png',
    colorMode: {
      defaultMode: 'light',
      disableSwitch: false,
      respectPrefersColorScheme: false,
    },
    navbar: {
      title: 'ANIP',
      logo: {
        alt: 'ANIP Logo',
        src: 'img/anip-logo-mark.png',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          position: 'left',
          label: 'Docs',
        },
        {to: '/docs/getting-started/install', label: 'Install', position: 'left'},
        {to: '/docs/releases/version-history', label: 'Versions', position: 'left'},
        {to: '/blog', label: 'Blog', position: 'left'},
        {href: 'https://playground.anip.dev', label: 'Playground', position: 'right'},
        {href: 'https://studio.anip.dev', label: 'Studio', position: 'right'},
        {
          href: 'https://github.com/anip-protocol/anip',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Docs',
          items: [
            {
              label: 'Why ANIP',
              to: '/docs/intro',
            },
            {
              label: 'Install',
              to: '/docs/getting-started/install',
            },
            {
              label: 'Feature Map',
              to: '/docs/feature-map',
            },
          ],
        },
        {
          title: 'Protocol',
          items: [
            {
              label: 'Capabilities',
              to: '/docs/protocol/capabilities',
            },
            {
              label: 'Delegation',
              to: '/docs/protocol/delegation-permissions',
            },
            {
              label: 'Audit and Trust',
              to: '/docs/protocol/checkpoints-trust',
            },
          ],
        },
        {
          title: 'Ecosystem',
          items: [
            {
              label: 'Studio',
              to: '/docs/tooling/studio',
            },
            {
              label: 'Showcases',
              to: '/docs/tooling/showcases',
            },
            {
              label: 'Distribution',
              to: '/docs/releases/what-ships-today',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} ANIP Protocol.`,
    },
    algolia: {
      appId: 'WTD3QO6JFS',
      apiKey: '867354f06b4f277fcfcbe40e0038a0cb',
      indexName: 'ANIP Documentation',
    },
    prism: {
      theme: prismThemes.vsLight,
      darkTheme: prismThemes.vsDark,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
