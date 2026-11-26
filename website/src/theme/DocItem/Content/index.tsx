import type {ReactNode} from 'react';
import Link from '@docusaurus/Link';
import Content from '@theme-original/DocItem/Content';
import type ContentType from '@theme/DocItem/Content';
import type {WrapperProps} from '@docusaurus/types';

type Props = WrapperProps<typeof ContentType>;

// Every docs page documents the frozen ANIP protocol; say so above its content.
export default function ContentWrapper(props: Props): ReactNode {
  return (
    <>
      <div className="alert alert--secondary margin-bottom--lg" role="note">
        <strong>ANIP protocol (frozen).</strong> This page documents ANIP, which receives
        security fixes only; the latest is{' '}
        <Link to="/docs/releases/approval-policy-enforcement-0-24-20">0.24.20</Link>. Its ideas
        are moving into MCP: <Link to="/">see what changed and what comes next</Link>.
      </div>
      <Content {...props} />
    </>
  );
}
