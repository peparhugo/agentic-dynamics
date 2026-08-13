import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { basename, dirname, extname, join, relative } from 'node:path';
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

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function metadataDate(value: unknown): string | undefined {
  if (value === undefined) return undefined;
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  return String(value);
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(path);
    return ['.md', '.markdown'].includes(extname(entry.name).toLowerCase()) ? [path] : [];
  }));
  return files.flat();
}

function pageFromSource(source: string, file: string, contentDir: string): Page {
  const parsed = matter(source);
  const relativePath = relative(contentDir, file).replace(/\\/g, '/');
  const slug = relativePath.replace(/\.(md|markdown)$/i, '');
  const fallbackTitle = basename(slug);
  const metadata = parsed.data as { title?: unknown; date?: unknown; tags?: unknown };
  const tags = Array.isArray(metadata.tags) ? metadata.tags.map(String) : [];

  return {
    title: typeof metadata.title === 'string' ? metadata.title : fallbackTitle,
    date: metadataDate(metadata.date),
    tags,
    slug,
    html: marked.parse(parsed.content) as string,
  };
}

function layout(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escapeHtml(title)}</title></head>\n<body>\n${body}\n</body>\n</html>\n`;
}

function pageHtml(page: Page): string {
  const details = [page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '', page.tags.length ? `<p>Tags: ${page.tags.map(escapeHtml).join(', ')}</p>` : ''].filter(Boolean).join('\n');
  return layout(page.title, `<article>\n<h1>${escapeHtml(page.title)}</h1>\n${details}\n${page.html}</article>`);
}

function indexHtml(pages: Page[]): string {
  const items = pages.map((page) => `<li><a href="${encodeURI(`${page.slug}.html`)}">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n');
  return layout('Index', `<main>\n<h1>Pages</h1>\n<ul>\n${items}\n</ul>\n</main>`);
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = options.contentDir ?? './content';
  const outputDir = options.outputDir ?? './dist';
  const files = await markdownFiles(contentDir);
  const pages = (await Promise.all(files.map(async (file) => pageFromSource(await readFile(file, 'utf8'), file, contentDir))))
    .sort((left, right) => left.title.localeCompare(right.title));

  await rm(outputDir, { recursive: true, force: true });
  await mkdir(outputDir, { recursive: true });
  await Promise.all(pages.map(async (page) => {
    const destination = join(outputDir, `${page.slug}.html`);
    await mkdir(dirname(destination), { recursive: true });
    await writeFile(destination, pageHtml(page));
  }));
  await writeFile(join(outputDir, 'index.html'), indexHtml(pages));
  return pages;
}
