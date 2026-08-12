import { promises as fs } from 'node:fs';
import { createHash } from 'node:crypto';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import type { Plugin, BuildContext, CacheEntry } from '../plugin';
import type { Page } from '../generator';

const asString = (value: unknown): string | undefined => typeof value === 'string' ? value : undefined;
const asDateString = (value: unknown): string | undefined => {
  if (typeof value === 'string') return value;
  if (value instanceof Date && !Number.isNaN(value.valueOf())) return value.toISOString().slice(0, 10);
  return undefined;
};
const asTags = (value: unknown): string[] => {
  if (Array.isArray(value)) return value.filter((tag): tag is string => typeof tag === 'string');
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
};

async function files(directory: string, relative = ''): Promise<string[]> {
  const entries = await fs.readdir(path.join(directory, relative), { withFileTypes: true });
  const result: string[] = [];
  for (const entry of entries) {
    const name = path.join(relative, entry.name);
    if (entry.isDirectory()) result.push(...await files(directory, name));
    else if (entry.isFile() && /\.md$/i.test(entry.name)) result.push(name);
  }
  return result;
}

export async function readPages(contentDir: string, cachedEntries: Record<string, CacheEntry> = {}): Promise<Page[]> {
  const names = (await files(contentDir)).sort();
  return Promise.all(names.map(async (sourcePath) => {
    const source = await fs.readFile(path.join(contentDir, sourcePath), 'utf8');
    const sourceHash = createHash('sha256').update(source).digest('hex');
    const cached = cachedEntries[sourcePath];
    if (cached?.sourceHash === sourceHash) return { ...cached.page, sourcePath };
    const parsed = matter(source);
    const title = asString(parsed.data.title) ?? path.basename(sourcePath, path.extname(sourcePath));
    return {
      sourcePath,
      outputPath: `${sourcePath.slice(0, -path.extname(sourcePath).length)}.html`,
      title,
      date: asDateString(parsed.data.date),
      tags: asTags(parsed.data.tags),
      html: await marked.parse(parsed.content),
      template: asString(parsed.data.template),
      layout: asString(parsed.data.layout),
      frontmatter: parsed.data
    };
  }));
}

export function MarkdownPlugin(): Plugin {
  return { name: 'markdown', async onStart(context: BuildContext) { context.pages = await readPages(context.contentDir, context.cache?.entries); } };
}

export default MarkdownPlugin;
