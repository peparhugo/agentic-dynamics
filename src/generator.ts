import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { basename, extname, join, relative, resolve, sep } from 'node:path';
import matter from 'gray-matter';
import MarkdownIt from 'markdown-it';

export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
}

export interface BuildOptions {
  content?: string;
  output?: string;
}

const markdown = new MarkdownIt();

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

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

export async function readPages(contentDirectory: string): Promise<Page[]> {
  const files = await markdownFiles(contentDirectory);
  const pages = await Promise.all(files.map(async (filePath) => {
    const parsed = matter(await readFile(filePath, 'utf8'));
    const fileSlug = relative(contentDirectory, filePath).split(sep).join('/').replace(/\.md$/i, '');
    const title = toStringValue(parsed.data.title) ?? basename(fileSlug);
    return {
      slug: fileSlug,
      title,
      date: toStringValue(parsed.data.date),
      tags: getTags(parsed.data.tags),
      html: markdown.render(parsed.content),
    };
  }));
  return pages.sort((a, b) => a.title.localeCompare(b.title));
}

function renderPage(page: Page): string {
  const metadata = [
    page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '',
    page.tags.length > 0 ? `<p class="tags">${page.tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join(' ')}</p>` : '',
  ].filter(Boolean).join('\n');
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escapeHtml(page.title)}</title></head>
<body>
<main>
<nav><a href="/index.html">Home</a></nav>
<article>
<h1>${escapeHtml(page.title)}</h1>
${metadata}
${page.html}
</article>
</main>
</body>
</html>
`;
}

function renderIndex(pages: Page[]): string {
  const links = pages.map((page) => `<li><a href="/${escapeHtml(page.slug)}.html">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n');
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Pages</title></head>
<body><main><h1>Pages</h1><ul>${links}</ul></main></body>
</html>
`;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDirectory = resolve(options.content ?? 'content');
  const outputDirectory = resolve(options.output ?? 'dist');
  const pages = await readPages(contentDirectory);
  await rm(outputDirectory, { recursive: true, force: true });
  await mkdir(outputDirectory, { recursive: true });
  await Promise.all(pages.map(async (page) => {
    const target = join(outputDirectory, `${page.slug}.html`);
    await mkdir(join(target, '..'), { recursive: true });
    await writeFile(target, renderPage(page), 'utf8');
  }));
  await writeFile(join(outputDirectory, 'index.html'), renderIndex(pages), 'utf8');
  return pages;
}
