import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  slug: string;
  html: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
}

type Metadata = Record<string, unknown>;

function metadataFromFrontmatter(parsed: unknown): Metadata {
  const result = parsed as { data?: unknown; frontmatter?: unknown };
  if (Array.isArray(result.frontmatter)) {
    return Object.fromEntries(
      result.frontmatter.filter((entry): entry is [string, unknown] =>
        Array.isArray(entry) && typeof entry[0] === 'string'
      )
    );
  }
  return typeof result.data === 'object' && result.data !== null
    ? result.data as Metadata
    : {};
}

function asString(value: unknown): string | undefined {
  if (typeof value === 'string') return value;
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  return undefined;
}

function asTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((tag): tag is string => typeof tag === 'string');
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function document(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>${escapeHtml(title)}</title>\n</head>\n<body>\n${body}\n</body>\n</html>\n`;
}

async function renderMarkdown(source: string): Promise<string> {
  const rendered = await marked.parse(source);
  if (typeof rendered === 'string') return rendered;
  const result = rendered as unknown as { html?: unknown };
  if (typeof result.html === 'string') return result.html;
  throw new Error('Markdown parser did not return HTML');
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './site');
  const entries = await fs.readdir(contentDir, { withFileTypes: true });
  const markdownFiles = entries.filter((entry) => entry.isFile() && /\.md$/i.test(entry.name));
  const pages = await Promise.all(markdownFiles.map(async (entry): Promise<Page> => {
    const source = await fs.readFile(path.join(contentDir, entry.name), 'utf8');
    const parsed = matter(source);
    const metadata = metadataFromFrontmatter(parsed);
    const slug = path.basename(entry.name, path.extname(entry.name));
    return {
      title: asString(metadata.title) ?? slug,
      date: asString(metadata.date),
      tags: asTags(metadata.tags),
      slug,
      html: await renderMarkdown(parsed.content),
    };
  }));

  pages.sort((a, b) => a.slug.localeCompare(b.slug));
  await fs.mkdir(outputDir, { recursive: true });
  await Promise.all(pages.map((page) => fs.writeFile(
    path.join(outputDir, `${page.slug}.html`),
    document(page.title, `<article>\n<h1>${escapeHtml(page.title)}</h1>\n${page.html}</article>`)
  )));

  const links = pages.map((page) => {
    const details = [page.date, page.tags.length > 0 ? page.tags.join(', ') : undefined].filter(Boolean).join(' | ');
    return `<li><a href="${encodeURIComponent(page.slug)}.html">${escapeHtml(page.title)}</a>${details ? ` <small>${escapeHtml(details)}</small>` : ''}</li>`;
  }).join('\n');
  await fs.writeFile(path.join(outputDir, 'index.html'), document('Pages', `<main>\n<h1>Pages</h1>\n<ul>\n${links}\n</ul>\n</main>`));
  return pages;
}
