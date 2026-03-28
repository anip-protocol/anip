import type {ReactNode} from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import HomepageFeatures from '@site/src/components/HomepageFeatures';
import Heading from '@theme/Heading';

import styles from './index.module.css';

function HomepageHeader() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <header className={clsx('hero hero--primary', styles.heroBanner)}>
      <div className="container">
        <div className={styles.heroInner}>
          <div className={styles.eyebrow}>Agent-native execution, not just tool calling</div>
          <Heading as="h1" className="hero__title">
            {siteConfig.title}
          </Heading>
          <p className="hero__subtitle">{siteConfig.tagline}</p>
          <p className={styles.heroLead}>
            ANIP is a protocol for agent execution where permissions, side
            effects, rollback posture, cost, failure recovery, and auditability
            are explicit before an action runs.
          </p>
          <p className={styles.heroDetail}>
            REST and MCP can expose tools and interfaces, but they still leave
            critical execution context implicit. ANIP makes that context part of
            the contract.
          </p>
          <div className={styles.ctaRow}>
            <Link className="button button--secondary button--lg" to="/docs/intro">
              Read the docs
            </Link>
            <Link className="button button--outline button--lg" to="/docs/getting-started/install">
              Install ANIP
            </Link>
          </div>
          <div className={styles.metaGrid}>
            <div className={styles.metaCard}>
              <span className={styles.metaLabel}>Current protocol</span>
              <span className={styles.metaValue}>v0.11 with observability</span>
            </div>
            <div className={styles.metaCard}>
              <span className={styles.metaLabel}>Bindings</span>
              <span className={styles.metaValue}>HTTP, stdio, gRPC</span>
            </div>
            <div className={styles.metaCard}>
              <span className={styles.metaLabel}>Runtimes</span>
              <span className={styles.metaValue}>TS, Python, Java, Go, C#</span>
            </div>
            <div className={styles.metaCard}>
              <span className={styles.metaLabel}>Tooling</span>
              <span className={styles.metaValue}>Studio, conformance, contract tests</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}

export default function Home(): ReactNode {
  return (
    <Layout
      title="A protocol for explicit, governable agent execution"
      description="ANIP makes permissions, side effects, rollback posture, cost, failure recovery, and auditability explicit before an agent invokes.">
      <HomepageHeader />
      <main>
        <HomepageFeatures />
        <section className={styles.section}>
          <div className="container">
            <div className={styles.sectionGrid}>
              <div className={styles.sectionCard}>
                <Heading as="h2">What ANIP enables</Heading>
                <ul className={styles.sectionList}>
                  <li>Agents can inspect permissions before trying a sensitive action.</li>
                  <li>Service authors can declare whether an action is read-only, transactional, or irreversible.</li>
                  <li>Infra and internal platform services can expose recoverable failure guidance instead of opaque errors.</li>
                  <li>Teams can review what happened through audit logs, checkpoints, Studio, and testing tools.</li>
                  <li>One execution model can be exposed over HTTP, stdio, and gRPC.</li>
                </ul>
              </div>
              <div className={styles.sectionCard}>
                <Heading as="h2">Start here</Heading>
                <div className={styles.linkList}>
                  <Link to="/docs/getting-started/install">Install ANIP runtimes and packages</Link>
                  <Link to="/docs/getting-started/quickstart">Follow the quickstart</Link>
                  <Link to="/docs/tooling/studio">Inspect services with Studio</Link>
                  <Link to="/docs/tooling/showcases">Explore the showcase apps</Link>
                  <Link to="/docs/releases/what-ships-today">See what ships today</Link>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>
    </Layout>
  );
}
