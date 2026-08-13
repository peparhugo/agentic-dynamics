import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import type { Page } from '../generator';
import type { Plugin, PluginContext } from '../plugin';

function metadataString(value: unknown): string | undefined {
  if (typeof value === 'string') return value;
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  return undefined;
}

function templateName(value: unknown): string | undefined {
  const name = metadataString(value);
  return name ? name.replace(/\.hbs$/i, '') : undefined;
}

export async function parsePages(contentDir: string): Promise<Page[]> {
  const entries = await readdir(contentDir, { withFileTypes: true });
  const files = entries.filter((entry) => entry.isFile() && /\.md$/i.test(entry.name));
  const pages = await Promise.all(files.map(async (file) => {
    const source = await readFile(path.join(contentDir, file.name), 'utf8');
    const parsed = matter(source);
    const slug = path.basename(file.name, path.extname(file.name));
    const title = metadataString(parsed.data.title) ?? slug;
    const date = metadataString(parsed.data.date);
    const rawTags = parsed.data.tags;
    const tags = Array.isArray(rawTags) ? rawTags.filter((tag): tag is string => typeof tag === 'string') : [];
    return {
      slug,
      title,
      date,
      tags,
      html: await marked.parse(parsed.content),
      template: templateName(parsed.data.template),
      layout: templateName(parsed.data.layout),
      data: parsed.data,
    };
  }));
  return pages.sort((left, right) => (right.date ?? '').localeCompare(left.date ?? ''));
}

export class MarkdownPlugin implements Plugin {
  async beforeBuild(context: PluginContext): Promise<void> {
    context.pages = await parsePages(context.contentDir);
  }
}
