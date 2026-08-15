import matter from 'gray-matter';
import { marked } from 'marked';
import { parseFrontmatter } from './frontmatter';
import { Page, ParsedFrontmatter } from './types';

/**
 * Parse a Markdown source string into structured page data.
 *
 * gray-matter only parses JSON frontmatter, so we parse the `---`-delimited
 * YAML block ourselves and merge it into gray-matter's output before handing
 * the data to the renderer.
 */
export function parseMarkdown(source: string, sourcePath: string, slug: string): Page {
  const yamlData = parseFrontmatter(source);
  const gm = matter(source);
  const merged: ParsedFrontmatter = { ...(gm.data as ParsedFrontmatter), ...yamlData };

  const title = readString(merged.title) || slug;
  const date = readString(merged.date);
  const tags = readTags(merged.tags);

  const html = marked.parse(gm.content, { async: false }) as string;

  return {
    slug,
    title,
    date,
    tags,
    content: gm.content,
    html,
    sourcePath,
    data: merged,
    template: readString(merged.template),
    layout: readString(merged.layout),
  };
}

function readString(value: unknown): string | undefined {
  if (typeof value === 'string' && value.trim() !== '') {
    return value;
  }
  if (value instanceof Date) {
    return value.toISOString();
  }
  return undefined;
}

function readTags(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .map((tag) => String(tag).trim())
      .filter((tag) => tag.length > 0);
  }
  if (typeof value === 'string' && value.trim() !== '') {
    return value
      .split(',')
      .map((tag) => tag.trim())
      .filter((tag) => tag.length > 0);
  }
  return [];
}
