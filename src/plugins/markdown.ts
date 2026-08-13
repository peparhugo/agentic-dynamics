import { readdir, readFile } from 'node:fs/promises';
import { basename, extname, join, relative } from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import { createHash } from 'node:crypto';
import type { Page } from '../generator.js';
import type { BuildContext, Plugin } from '../plugin.js';

function metadataDate(value: unknown): string | undefined {
  if (value === undefined) return undefined;
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  return String(value);
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const file = join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(file);
    return ['.md', '.markdown'].includes(extname(entry.name).toLowerCase()) ? [file] : [];
  }));
  return files.flat();
}

function pageFromSource(source: string, file: string, contentDir: string): Page {
  const parsed = matter(source);
  const relativePath = relative(contentDir, file).replace(/\\/g, '/');
  const slug = relativePath.replace(/\.(md|markdown)$/i, '');
  const metadata = parsed.data as { title?: unknown; date?: unknown; tags?: unknown; template?: unknown; layout?: unknown };

  return {
    title: typeof metadata.title === 'string' ? metadata.title : basename(slug),
    date: metadataDate(metadata.date),
    tags: Array.isArray(metadata.tags) ? metadata.tags.map(String) : [],
    slug,
    html: marked.parse(parsed.content) as string,
    template: typeof metadata.template === 'string' ? metadata.template : undefined,
    layout: typeof metadata.layout === 'string' ? metadata.layout : undefined,
    sourcePath: file,
    sourceHash: createHash('sha256').update(source).digest('hex'),
  };
}

export class MarkdownPlugin implements Plugin {
  private static parsedPages = new Map<string, { hash: string; page: Page }>();

  async beforeBuild(context: BuildContext): Promise<void> {
    const files = await markdownFiles(context.options.contentDir);
    context.pages.push(...await Promise.all(files.map(async (file) => {
      const source = await readFile(file, 'utf8');
      const hash = createHash('sha256').update(source).digest('hex');
      const cached = MarkdownPlugin.parsedPages.get(file);
      if (cached?.hash === hash) return { ...cached.page };
      const page = pageFromSource(source, file, context.options.contentDir);
      MarkdownPlugin.parsedPages.set(file, { hash, page });
      return page;
    })));
    context.pages.sort((left, right) => left.title.localeCompare(right.title));
  }
}
