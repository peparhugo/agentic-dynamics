import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import type { BuildContext, Metadata, Plugin } from './types.js';

function metadataFromFrontmatter(parsed: unknown): Metadata {
  const result = parsed as { data?: unknown; frontmatter?: unknown };
  if (Array.isArray(result.frontmatter)) {
    return Object.fromEntries(result.frontmatter.filter((entry): entry is [string, unknown] => Array.isArray(entry) && typeof entry[0] === 'string'));
  }
  return typeof result.data === 'object' && result.data !== null ? result.data as Metadata : {};
}

function asString(value: unknown): string | undefined {
  if (typeof value === 'string') return value;
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  return undefined;
}

function asTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((tag): tag is string => typeof tag === 'string');
  return typeof value === 'string' ? value.split(',').map((tag) => tag.trim()).filter(Boolean) : [];
}

async function renderMarkdown(source: string): Promise<string> {
  const rendered = await marked.parse(source);
  if (typeof rendered === 'string') return rendered;
  const result = rendered as unknown as { html?: unknown };
  if (typeof result.html === 'string') return result.html;
  throw new Error('Markdown parser did not return HTML');
}

export class MarkdownPlugin implements Plugin {
  async beforeBuild(context: BuildContext): Promise<void> {
    context.sourcePages = await Promise.all(context.files.map(async (file) => {
      const cached = context.cachedSourcePages[file];
      if (cached && !context.filesToBuild.has(file)) return cached;
      const source = await fs.readFile(path.join(context.contentDir, file), 'utf8');
      const parsed = matter(source);
      const metadata = metadataFromFrontmatter(parsed);
      const slug = path.basename(file, path.extname(file));
      return { title: asString(metadata.title) ?? slug, date: asString(metadata.date), tags: asTags(metadata.tags), slug, html: await renderMarkdown(parsed.content), metadata, template: asString(metadata.template) };
    }));
    context.sourcePages.sort((left, right) => left.slug.localeCompare(right.slug));
    context.pages = context.sourcePages.map(({ metadata: _metadata, template: _template, ...page }) => page);
  }
}
