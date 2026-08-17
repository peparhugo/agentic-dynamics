import matter from 'gray-matter';
import * as yaml from 'js-yaml';
import { marked } from 'marked';

export interface Frontmatter {
  title?: string;
  date?: string;
  tags?: string[] | string;
}

export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
}

const FRONTMATTER_DELIMITER = /^\uFEFF?---\s*\r?\n([\s\S]*?)\r?\n---\s*(?:\r?\n|$)/;

/**
 * Parse YAML frontmatter from a raw markdown file and return the metadata
 * plus the stripped markdown body. The frontmatter block is stripped here so
 * that it is never passed to the markdown renderer.
 */
export function parseFrontmatter(raw: string): { frontmatter: Frontmatter; content: string } {
  const normalized = raw.replace(/^\uFEFF/, '');
  let parsed: { data: Record<string, unknown>; content: string };

  if (FRONTMATTER_DELIMITER.test(normalized)) {
    parsed = matter(normalized, {
      engines: {
        yaml: {
          parse: (str: string) => yaml.load(str, { schema: yaml.JSON_SCHEMA }) as Record<string, unknown>,
          stringify: (obj: unknown) => yaml.dump(obj, { schema: yaml.JSON_SCHEMA }),
        },
      },
    });
  } else {
    parsed = { data: {}, content: normalized };
  }

  return {
    frontmatter: parsed.data as Frontmatter,
    content: parsed.content,
  };
}

/** Normalize a tags value (string or array) into a string array. */
export function normalizeTags(tags: Frontmatter['tags']): string[] {
  if (tags == null) {
    return [];
  }
  if (Array.isArray(tags)) {
    return tags.map((t) => String(t).trim()).filter((t) => t.length > 0);
  }
  return String(tags)
    .split(',')
    .map((t) => t.trim())
    .filter((t) => t.length > 0);
}

/** Convert a markdown body to HTML. */
export function markdownToHtml(markdown: string): string {
  return marked.parse(markdown, { async: false }) as string;
}
