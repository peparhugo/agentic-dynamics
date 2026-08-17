import matter from 'gray-matter';
import { marked } from 'marked';
import { Frontmatter } from './types';

// Matches a YAML frontmatter block. The opening `---` may be preceded only by
// optional leading whitespace so that marked never sees the delimiters.
const FRONTMATTER_REGEX = /^\s*---[ \t]*\r?\n([\s\S]*?)\r?\n---[ \t]*\r?\n?/;

/**
 * Split raw markdown into frontmatter data and the markdown body.
 *
 * The frontmatter block is stripped manually with a regex before the body is
 * handed to `marked`, otherwise `marked` renders the `---` delimiters as a
 * literal horizontal rule. gray-matter is used only to parse the YAML data.
 */
export function splitFrontmatter(raw: string): { data: Frontmatter; body: string } {
  const match = raw.match(FRONTMATTER_REGEX);
  if (!match) {
    return { data: {}, body: raw };
  }

  let data: Frontmatter = {};
  try {
    // gray-matter requires the opening `---` to be the very first bytes of its
    // input, so rebuild a clean block (leading whitespace already stripped).
    data = (matter(`---\n${match[1]}\n---`).data as Frontmatter) ?? {};
  } catch {
    data = {};
  }

  const body = raw.slice(match[0].length);
  return { data, body };
}

export function normalizeDate(value: unknown): string | undefined {
  if (value == null) return undefined;
  if (value instanceof Date) {
    return value.toISOString().slice(0, 10);
  }
  const str = String(value).trim();
  return str.length > 0 ? str : undefined;
}

/**
 * Parse raw markdown (with optional frontmatter) into frontmatter data and
 * rendered HTML. The returned HTML is a document fragment (no <html>/<body>).
 */
export function parseMarkdown(raw: string): { frontmatter: Frontmatter; html: string } {
  const { data, body } = splitFrontmatter(raw);
  const html = marked.parse(body, { async: false }) as string;
  return {
    frontmatter: { ...data, date: normalizeDate(data.date) },
    html,
  };
}

export function escapeHtml(input: string): string {
  return input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function normalizeTags(tags: unknown): string[] {
  if (Array.isArray(tags)) {
    return tags.map((t) => String(t));
  }
  if (typeof tags === 'string') {
    return tags
      .split(',')
      .map((t) => t.trim())
      .filter((t) => t.length > 0);
  }
  return [];
}

export function defaultTitle(slug: string): string {
  return slug
    .split(/[/\\-]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}
