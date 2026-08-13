import { readdir, readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { basename, extname, join, relative, sep } from 'node:path';
import matter from 'gray-matter';
import MarkdownIt from 'markdown-it';
import type { Page, Plugin, PluginContext } from '../plugin.js';

const markdown = new MarkdownIt();
const parsedPageCache = new Map<string, Page>();

function toStringValue(value: unknown): string | undefined {
  if (typeof value === 'string') return value;
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  return undefined;
}

function getTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((tag): tag is string => typeof tag === 'string');
  if (typeof value === 'string') return [value];
  return [];
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const filePath = join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(filePath);
    return extname(entry.name).toLowerCase() === '.md' ? [filePath] : [];
  }));
  return files.flat();
}

export class MarkdownPlugin implements Plugin {
  async beforeBuild({ contentDirectory, pages }: PluginContext): Promise<void> {
    const files = await markdownFiles(contentDirectory);
    const parsedPages = await Promise.all(files.map(async (filePath): Promise<Page> => {
      const source = await readFile(filePath, 'utf8');
      const sourceHash = createHash('sha256').update(source).digest('hex');
      const cached = parsedPageCache.get(filePath);
      if (cached?.sourceHash === sourceHash) return { ...cached };
      const parsed = matter(source);
      const slug = relative(contentDirectory, filePath).split(sep).join('/').replace(/\.md$/i, '');
      const page = {
        slug,
        title: toStringValue(parsed.data.title) ?? basename(slug),
        date: toStringValue(parsed.data.date),
        tags: getTags(parsed.data.tags),
        html: markdown.render(parsed.content),
        template: toStringValue(parsed.data.template),
        layout: parsed.data.layout === false ? false : toStringValue(parsed.data.layout),
        data: parsed.data,
        sourcePath: filePath,
        sourceHash,
      };
      parsedPageCache.set(filePath, page);
      return { ...page };
    }));
    pages.push(...parsedPages.sort((a, b) => a.title.localeCompare(b.title)));
  }
}
