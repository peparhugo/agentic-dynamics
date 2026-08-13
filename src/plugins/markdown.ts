import { readdir, readFile } from 'node:fs/promises';
import { relative, resolve } from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import type { PageData } from '../generator';
import type { Plugin, PluginContext } from '../plugin';

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const paths = await Promise.all(entries.map(async (entry) => {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(path);
    return entry.isFile() && /\.md$/i.test(entry.name) ? [path] : [];
  }));
  return paths.flat();
}

function dateValue(value: unknown): string | undefined {
  if (value === undefined || value === null) return undefined;
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  return String(value);
}

export class MarkdownPlugin implements Plugin {
  async beforeBuild(context: PluginContext): Promise<void> {
    const files = await markdownFiles(context.options.contentDir);
    context.sourcePages = await Promise.all(files.map(async (sourcePath) => {
      const parsed = matter(await readFile(sourcePath, 'utf8'));
      const data = parsed.data as PageData;
      const outputPath = relative(context.options.contentDir, sourcePath).replace(/\.md$/i, '.html');
      const title = typeof data.title === 'string' && data.title.trim()
        ? data.title
        : outputPath.replace(/\.html$/i, '');
      const page = {
        sourcePath,
        outputPath,
        title,
        date: dateValue(data.date),
        tags: Array.isArray(data.tags) ? data.tags.map(String) : [],
        html: await marked.parse(parsed.content)
      };
      return { page, data };
    }));
    context.pages = context.sourcePages.map(({ page }) => page).sort((a, b) => a.title.localeCompare(b.title));
  }
}
