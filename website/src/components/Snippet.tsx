import type {ReactNode} from 'react';
import CodeBlock from '@theme/CodeBlock';

type Props = {
  /** File contents, imported with `!!raw-loader!@site/snippets/...`. */
  src: string;
  language: string;
  title?: string;
  /** Show only the lines between `region: <name>` and `endregion` markers. */
  region?: string;
};

const MARKER = /^\s*(#|\/\/)\s*(region:|endregion)/;

/**
 * Shows a file, or one region of it, from `website/snippets`.
 *
 * Those files are run in CI against the published packages
 * (.github/workflows/ci-docs-snippets.yml), so what the page shows is what
 * was tested. Do not paste code into a page instead of using this.
 */
export default function Snippet({src, language, title, region}: Props): ReactNode {
  let lines = src.replace(/\n$/, '').split('\n');
  if (region) {
    const start = lines.findIndex((line) => MARKER.test(line) && line.includes(`region: ${region}`));
    const end = lines.findIndex((line, i) => i > start && /endregion/.test(line) && MARKER.test(line));
    if (start === -1 || end === -1) {
      throw new Error(`Snippet region "${region}" not found`);
    }
    lines = lines.slice(start + 1, end);
  }
  const code = lines.filter((line) => !MARKER.test(line)).join('\n');
  return (
    <CodeBlock language={language} title={title}>
      {code}
    </CodeBlock>
  );
}
