import matter from 'gray-matter';
import { marked } from 'marked';

export interface Frontmatter {
  [key: string]: unknown;
}

export interface ParsedDocument {
  frontmatter: Frontmatter;
  html: string;
  body: string;
}

const FRONTMATTER_RE = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/;

/**
 * Parse a Markdown document, splitting YAML frontmatter from the body.
 *
 * The frontmatter block is stripped manually with a regex before `marked` is
 * invoked, so that `marked` never sees the leading `---` delimiters (which it
 * would otherwise render as a literal horizontal rule).
 *
 * gray-matter is then used to parse the YAML payload itself.
 */
export function parseMarkdown(raw: string): ParsedDocument {
  const match = raw.match(FRONTMATTER_RE);

  let frontmatter: Frontmatter = {};
  let body = raw;

  if (match) {
    body = raw.slice(match[0].length);
    const parsed = matter(match[0]);
    frontmatter = (parsed.data ?? {}) as Frontmatter;
  }

  const html = marked.parse(body) as string;
  return { frontmatter, html, body };
}
