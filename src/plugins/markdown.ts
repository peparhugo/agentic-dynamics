import { promises as fs } from 'node:fs';
import matter from 'gray-matter';
import { marked } from 'marked';
import type { Frontmatter, GeneratedPage, ParsedMarkdown, Plugin } from '../types';

function parseScalar(value: string): unknown {
  const trimmed = value.trim();
  if (!trimmed) return '';
  if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
    return trimmed.slice(1, -1).split(',').map((item) => String(parseScalar(item))).filter(Boolean);
  }
  if ((trimmed.startsWith('"') && trimmed.endsWith('"')) ||
      (trimmed.startsWith("'") && trimmed.endsWith("'"))) return trimmed.slice(1, -1);
  if (trimmed === 'true') return true;
  if (trimmed === 'false') return false;
  if (trimmed === 'null') return null;
  if (/^-?\d+(\.\d+)?$/.test(trimmed)) return Number(trimmed);
  return trimmed;
}

function parseYamlFrontmatter(source: string): { data: Frontmatter; content: string } {
  const normalized = source.replace(/^\uFEFF/, '');
  const match = normalized.match(/^---[ \t]*\r?\n([\s\S]*?)\r?\n---[ \t]*(?:\r?\n|$)/);
  if (!match) return { data: {}, content: source };
  const data: Frontmatter = {};
  let listKey: string | undefined;
  for (const rawLine of match[1].split(/\r?\n/)) {
    const listItem = rawLine.match(/^\s+-\s+(.+)$/);
    if (listItem && listKey) {
      const current = data[listKey];
      data[listKey] = [...(Array.isArray(current) ? current : []), String(parseScalar(listItem[1]))];
      continue;
    }
    const entry = rawLine.match(/^\s*([^#:][^:]*):\s*(.*?)\s*$/);
    if (!entry) continue;
    const key = entry[1].trim();
    data[key] = entry[2] === '' ? [] : parseScalar(entry[2]);
    listKey = entry[2] === '' ? key : undefined;
  }
  return { data, content: normalized.slice(match[0].length) };
}

function normalizeFrontmatter(data: Record<string, unknown>): Frontmatter {
  const normalized: Frontmatter = { ...data };
  if (data.title != null) normalized.title = String(data.title);
  if (data.date instanceof Date) normalized.date = data.date.toISOString();
  else if (data.date != null) normalized.date = String(data.date);
  if (typeof data.tags === 'string') normalized.tags = data.tags.split(',').map((tag) => tag.trim()).filter(Boolean);
  else if (Array.isArray(data.tags)) normalized.tags = data.tags.map(String);
  return normalized;
}

export function parseMarkdown(source: string): ParsedMarkdown {
  const yaml = parseYamlFrontmatter(source);
  const parsed = matter(yaml.content);
  const data = normalizeFrontmatter({ ...parsed.data, ...yaml.data });
  return { data, content: parsed.content, html: marked.parse(parsed.content) as string };
}

export class MarkdownPlugin implements Plugin {
  readonly name = 'markdown';

  async onFile(page: GeneratedPage): Promise<void> {
    const parsed = parseMarkdown(await fs.readFile(page.sourcePath, 'utf8'));
    Object.assign(page, parsed, { title: parsed.data.title || page.title });
  }
}
