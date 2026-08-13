import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import Handlebars from 'handlebars';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  template?: string;
  layout?: string;
  data: Record<string, unknown>;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>'"]/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
  }[character] as string));
}

function pageDocument(page: Page): string {
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escapeHtml(page.title)}</title></head>
<body><main><h1>${escapeHtml(page.title)}</h1>${page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}${page.tags.length ? `<p>Tags: ${page.tags.map(escapeHtml).join(', ')}</p>` : ''}${page.html}</main></body>
</html>`;
}

function indexDocument(pages: Page[]): string {
  const items = pages.map((page) => `<li><a href="${encodeURIComponent(page.slug)}.html">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n');
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Pages</title></head>
<body><main><h1>Pages</h1><ul>${items}</ul></main></body>
</html>`;
}

function metadataString(value: unknown): string | undefined {
  if (typeof value === 'string') return value;
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  return undefined;
}

function templateName(value: unknown): string | undefined {
  const name = metadataString(value);
  return name ? name.replace(/\.hbs$/i, '') : undefined;
}

async function readTemplate(directory: string, name: string): Promise<string | undefined> {
  try {
    return await readFile(path.join(directory, `${name}.hbs`), 'utf8');
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return undefined;
    throw error;
  }
}

async function registerPartials(templatesDir: string, handlebars: ReturnType<typeof Handlebars.create>): Promise<void> {
  const partialsDir = path.join(templatesDir, 'partials');
  try {
    const entries = await readdir(partialsDir, { withFileTypes: true });
    await Promise.all(entries.filter((entry) => entry.isFile() && /\.hbs$/i.test(entry.name)).map(async (entry) => {
      const name = path.basename(entry.name, '.hbs');
      handlebars.registerPartial(name, await readFile(path.join(partialsDir, entry.name), 'utf8'));
    }));
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
  }
}

async function renderPage(page: Page, templatesDir: string, handlebars: ReturnType<typeof Handlebars.create>): Promise<string> {
  const context = { ...page.data, ...page, body: page.html };
  const source = await readTemplate(templatesDir, page.template ?? 'default');
  const body = source ? handlebars.compile(source)(context) : pageDocument(page);
  const layout = page.layout ?? 'default';
  const layoutSource = await readTemplate(path.join(templatesDir, 'layouts'), layout);
  return layoutSource ? handlebars.compile(layoutSource)({ ...context, body }) : body;
}

export async function readPages(contentDir: string): Promise<Page[]> {
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

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? 'content');
  const outputDir = path.resolve(options.outputDir ?? 'dist');
  const templatesDir = path.resolve(options.templatesDir ?? 'templates');
  const pages = await readPages(contentDir);
  const handlebars = Handlebars.create();
  await registerPartials(templatesDir, handlebars);
  await rm(outputDir, { recursive: true, force: true });
  await mkdir(outputDir, { recursive: true });
  await Promise.all(pages.map(async (page) => writeFile(path.join(outputDir, `${page.slug}.html`), await renderPage(page, templatesDir, handlebars))));
  await writeFile(path.join(outputDir, 'index.html'), indexDocument(pages));
  return pages;
}
