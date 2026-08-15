import { basename, sep } from 'node:path';
import matter from 'gray-matter';
import MarkdownIt from 'markdown-it';
import type { Plugin } from '../plugin';
import type { Page } from '../site';

type Frontmatter = Record<string, string | string[]>;
const markdown = new MarkdownIt({ html: true });

function parseYamlFrontmatter(source: string): Frontmatter {
  const match = source.match(/^---\s*\r?\n([\s\S]*?)\r?\n---\s*(?:\r?\n|$)/);
  if (!match) return {};
  return match[1].split(/\r?\n/).reduce<Frontmatter>((data, line) => {
    const separator = line.indexOf(':');
    if (separator === -1) return data;
    const key = line.slice(0, separator).trim();
    const value = line.slice(separator + 1).trim();
    if (!key) return data;
    const unquoted = value.replace(/^(?:"|')|(?:"|')$/g, '');
    data[key] = unquoted.startsWith('[') && unquoted.endsWith(']')
      ? unquoted.slice(1, -1).split(',').map((tag) => tag.trim().replace(/^(?:"|')|(?:"|')$/g, '')).filter(Boolean)
      : unquoted;
    return data;
  }, {});
}

function stringValue(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

function tagValues(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((tag): tag is string => typeof tag === 'string');
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

export function parsePage(source: string, filename: string): Page {
  const parsed = matter(source);
  const data = { ...parsed.data, ...parseYamlFrontmatter(source) };
  const fallbackTitle = basename(filename, '.md').replace(/[-_]/g, ' ');
  return {
    title: stringValue(data.title) ?? fallbackTitle,
    date: stringValue(data.date),
    tags: tagValues(data.tags),
    slug: basename(filename, '.md'),
    html: markdown.render(parsed.content),
    template: stringValue(data.template),
    layout: stringValue(data.layout),
    frontmatter: data,
  };
}

export const MarkdownPlugin: Plugin = {
  onFile(context) {
    if (context.source === undefined || context.filename === undefined) return;
    context.page = parsePage(context.source, context.filename);
    context.page.slug = context.filename.replace(/\.md$/i, '').split(sep).join('/');
  },
};
