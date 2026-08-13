import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import type { BuildContext, Plugin } from '../plugin.js';
import type { Page } from '../site.js';

function valueToString(value: unknown): string | undefined {
  if (value === undefined || value === null) return undefined;
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  return String(value);
}

function toTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

async function filesIn(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const fullPath = path.join(directory, entry.name);
    return entry.isDirectory() ? filesIn(fullPath) : [fullPath];
  }));
  return files.flat();
}

export class MarkdownPlugin implements Plugin {
  async beforeBuild(context: BuildContext): Promise<void> {
    const files = (await filesIn(context.contentDir)).filter((filePath) => /\.md$/i.test(filePath));
    context.pages = await Promise.all(files.map(async (sourcePath): Promise<Page> => {
      const parsed = matter(await fs.readFile(sourcePath, 'utf8'));
      const relativePath = path.relative(context.contentDir, sourcePath);
      const outputPath = path.join(context.outputDir, relativePath.replace(/\.md$/i, '.html'));
      return {
        sourcePath,
        outputPath,
        url: `/${path.relative(context.outputDir, outputPath).split(path.sep).join('/')}`,
        title: valueToString(parsed.data.title) ?? path.basename(relativePath, path.extname(relativePath)),
        date: valueToString(parsed.data.date),
        tags: toTags(parsed.data.tags),
        html: await marked.parse(parsed.content),
        template: valueToString(parsed.data.template),
      };
    }));
    context.pages.sort((left, right) => (right.date ?? '').localeCompare(left.date ?? '') || left.title.localeCompare(right.title));
  }
}
