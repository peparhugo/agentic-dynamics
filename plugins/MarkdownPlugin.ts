import { basename, extname } from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import type { Page } from '../src/generator';
import type { Plugin } from '../src/plugin';

type Frontmatter = Record<string, string | string[]>;
const parsedPages = new Map<string, Page>();

/** Parse the deliberately small YAML subset supported by this generator. */
function parseYaml(block: string): Frontmatter {
  const data: Frontmatter = {};
  for (const line of block.split(/\r?\n/)) {
    const match = line.match(/^([\w-]+):\s*(.*)$/);
    if (!match) continue;
    const [, key, rawValue] = match;
    const value = rawValue.trim().replace(/^(["'])(.*)\1$/, '$2');
    data[key] = value.startsWith('[') && value.endsWith(']')
      ? value.slice(1, -1).split(',').map((tag) => tag.trim().replace(/^(["'])(.*)\1$/, '$2')).filter(Boolean)
      : value;
  }
  return data;
}

function extractYaml(source: string): Frontmatter {
  const match = source.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
  return match ? parseYaml(match[1]) : {};
}

export function parsePage(source: string, filePath: string): Page {
  const cacheKey = `${filePath}\0${source}`;
  const cached = parsedPages.get(cacheKey);
  if (cached) return { ...cached, tags: [...cached.tags] };
  const parsed = matter(source);
  const data = { ...parsed.data, ...extractYaml(source) } as Frontmatter;
  const name = basename(filePath, extname(filePath));
  const tags = data.tags === undefined ? [] : Array.isArray(data.tags)
    ? data.tags
    : data.tags.split(',').map((tag) => tag.trim()).filter(Boolean);

  const page = {
    title: typeof data.title === 'string' ? data.title : name,
    date: typeof data.date === 'string' ? data.date : undefined,
    tags,
    slug: name,
    html: marked.parse(parsed.content) as string,
    template: typeof data.template === 'string' ? data.template : undefined,
    layout: typeof data.layout === 'string' ? data.layout : undefined,
  };
  parsedPages.set(cacheKey, page);
  return { ...page, tags: [...page.tags] };
}

export const MarkdownPlugin: Plugin = {
  onFile(page, context) {
    if (!context.file) return;
    Object.assign(page, parsePage(context.file.source, context.file.path));
  },
};
