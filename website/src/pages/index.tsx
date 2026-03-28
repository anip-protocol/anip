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
            ANIP gives agents the context REST and MCP leave implicit:
            authority, permissions, side effects, rollback posture, cost,
            failure recovery, auditability, and transport-neutral execution.
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
  const {siteConfig} = useDocusaurusContext();
  return (
    <Layout
      title="Protocol, runtimes, tooling, and examples for agent-native interfaces"
      description="ANIP explains what an agent is allowed to do before it invokes, not after it fails. Learn the protocol, transports, examples, Studio, and release surface.">
      <HomepageHeader />
      <main>
        <HomepageFeatures />
        <section className={styles.section}>
          <div className="container">
            <div className={styles.sectionGrid}>
              <div className={styles.sectionCard}>
                <Heading as="h2">Why teams adopt ANIP</Heading>
                <ul className={styles.sectionList}>
                  <li>Agents can inspect permissions before invoke.</li>
                  <li>Side effects and rollback posture are declared instead of guessed.</li>
                  <li>Failures describe what blocked the action and how to recover.</li>
                  <li>Audit logs and checkpoints make execution reviewable.</li>
                  <li>One service can expose native ANIP plus REST, GraphQL, and MCP surfaces.</li>
                </ul>
              </div>
              <div className={styles.sectionCard}>
                <Heading as="h2">What ships today</Heading>
                <pre>
                  <code>{`TypeScript  npm packages
Python      PyPI packages
Java        Maven Central
Go          module tags
C#          in-repo runtime
Studio      embedded + standalone
Testing     conformance + contract tests`}</code>
                </pre>
              </div>
            </div>
          </div>
        </section>
      </main>
    </Layout>
  );
}
