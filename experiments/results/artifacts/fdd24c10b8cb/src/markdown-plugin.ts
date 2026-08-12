import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import { Frontmatter, Page } from './types';
import { Plugin, PluginContext } from './plugin';

function asString(value: unknown): string | undefined {
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  return undefined;
}

function normalizeTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

function normalizeFrontmatter(data: Record<string, unknown>, fallbackTitle: string): Frontmatter {
  const result: Frontmatter = { title: asString(data.title) || fallbackTitle, date: asString(data.date), tags: normalizeTags(data.tags) };
  const template = asString(data.template);
  const layout = asString(data.layout);
  if (template) result.template = template;
  if (layout) result.layout = layout;
  return result;
}

function titleFromFilename(filePath: string): string {
  return path.basename(filePath, path.extname(filePath)).replace(/[-_]+/g, ' ').replace(/\b\w/g, (character) => character.toUpperCase());
}

export async function parseMarkdown(sourcePath: string, content: string, contentDir?: string): Promise<Page> {
  const parsed = matter(content);
  const relativePath = contentDir ? path.relative(contentDir, sourcePath) : path.basename(sourcePath);
  const slug = relativePath.replace(/\\/g, '/').replace(/\.md$/i, '');
  return { sourcePath, outputPath: `${slug}.html`, slug, frontmatter: normalizeFrontmatter(parsed.data as Record<string, unknown>, titleFromFilename(sourcePath)), html: await marked.parse(parsed.content) };
}

export class MarkdownPlugin implements Plugin {
  async onFile(page: Page, context: PluginContext): Promise<Page> {
    return parseMarkdown(page.sourcePath, page.html, context.contentDir);
  }
}

export async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(entryPath));
    else if (entry.isFile() && /\.md$/i.test(entry.name)) files.push(entryPath);
  }
  return files.sort((a, b) => a.localeCompare(b));
}
