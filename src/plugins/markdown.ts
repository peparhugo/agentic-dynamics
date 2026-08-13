import { readdir, readFile } from 'node:fs/promises';
import { basename, extname, join, relative, sep } from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import { BuildContext, Plugin } from '../plugin';

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const paths = await Promise.all(entries.map(async (entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(path);
    return entry.isFile() && ['.md', '.markdown'].includes(extname(entry.name).toLowerCase()) ? [path] : [];
  }));
  return paths.flat();
}

function asString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

function asTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((tag): tag is string => typeof tag === 'string').map((tag) => tag.trim()).filter(Boolean);
  return typeof value === 'string' ? value.split(',').map((tag) => tag.trim()).filter(Boolean) : [];
}

export class MarkdownPlugin implements Plugin {
  async beforeBuild(context: BuildContext): Promise<void> {
    const files = await markdownFiles(context.contentDir);
    context.pages = await Promise.all(files.map(async (file) => {
      const parsed = matter(await readFile(file, 'utf8'));
      const sourcePath = relative(context.contentDir, file);
      return {
        title: asString(parsed.data.title) ?? basename(file, extname(file)),
        date: asString(parsed.data.date),
        tags: asTags(parsed.data.tags),
        outputPath: sourcePath.replace(/\.(md|markdown)$/i, '.html').split(sep).join('/'),
        html: await marked.parse(parsed.content),
        template: asString(parsed.data.template),
        layout: asString(parsed.data.layout),
        data: parsed.data,
      };
    }));
    context.pages.sort((a, b) => a.title.localeCompare(b.title));
  }
}
