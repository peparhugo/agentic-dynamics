import matter from 'gray-matter';

export interface ParsedMarkdown {
  data: Record<string, unknown>;
  content: string;
}

const FRONTMATTER_RE = /^---[ \t]*\r?\n([\s\S]*?)\r?\n---[ \t]*(?:\r?\n|$)/;

function stripBom(raw: string): string {
  return raw.charCodeAt(0) === 0xfeff ? raw.slice(1) : raw;
}

/**
 * Parse a raw Markdown file: extract YAML frontmatter (if present) and return
 * the parsed data alongside the remaining Markdown body.
 *
 * The frontmatter block is stripped manually with a regex before the body is
 * handed to a Markdown parser, so `---` delimiters are never rendered as HTML.
 */
export function parseMarkdown(raw: string): ParsedMarkdown {
  const text = stripBom(raw);
  const match = text.match(FRONTMATTER_RE);

  if (!match) {
    return { data: {}, content: text };
  }

  const yaml = match[1];
  const content = text.slice(match[0].length);
  const parsed = matter(`---\n${yaml}\n---`);

  return { data: parsed.data, content };
}
