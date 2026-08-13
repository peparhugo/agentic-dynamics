import { mkdir, readdir, readFile, rm, stat, writeFile } from 'node:fs/promises';
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
  return value.replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  })[character] ?? character);
}

function toDateString(value: unknown): string | undefined {
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === 'string' && value.trim()) return value;
  return undefined;
}

function toTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((tag): tag is string => typeof tag === 'string');
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

function toTemplateName(value: unknown): string | undefined {
  if (typeof value !== 'string' || !value.trim()) return undefined;
  const name = value.trim().replace(/\.hbs$/i, '');
  if (name.includes('/') || name.includes('\\') || name === '.' || name === '..') {
    throw new Error(`Invalid template name: ${value}`);
  }
  return name;
}

async function directoryExists(directory: string): Promise<boolean> {
  try {
    return (await stat(directory)).isDirectory();
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return false;
    throw error;
  }
}

async function loadPartials(templatesDir: string): Promise<void> {
  const partialsDir = path.join(templatesDir, 'partials');
  if (!await directoryExists(partialsDir)) return;
  const entries = await readdir(partialsDir, { withFileTypes: true });
  await Promise.all(entries
    .filter((entry) => entry.isFile() && /\.hbs$/i.test(entry.name))
    .map(async (entry) => {
      const name = entry.name.replace(/\.hbs$/i, '');
      Handlebars.registerPartial(name, await readFile(path.join(partialsDir, entry.name), 'utf8'));
    }));
}

async function renderTemplate(templatesDir: string, name: string, context: object): Promise<string> {
  const templatePath = path.join(templatesDir, `${name}.hbs`);
  let source: string;
  try {
    source = await readFile(templatePath, 'utf8');
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') throw new Error(`Template not found: ${name}`);
    throw error;
  }
  return Handlebars.compile(source)(context);
}

function pageDocument(page: Page): string {
  const date = page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
  const tags = page.tags.length > 0
    ? `<ul class="tags">${page.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>`
    : '';
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escapeHtml(page.title)}</title></head>
<body><main><nav><a href="index.html">Home</a></nav><article><h1>${escapeHtml(page.title)}</h1>${date}${tags}${page.html}</article></main></body>
</html>`;
}

function indexDocument(pages: Page[]): string {
  const items = pages.map((page) => {
    const date = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
    return `<li><a href="${encodeURIComponent(page.slug)}.html">${escapeHtml(page.title)}</a>${date}</li>`;
  }).join('');
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Pages</title></head>
<body><main><h1>Pages</h1><ul>${items}</ul></main></body>
</html>`;
}

export async function readPages(contentDir: string): Promise<Page[]> {
  const entries = await readdir(contentDir, { withFileTypes: true });
  const markdownFiles = entries.filter((entry) => entry.isFile() && /\.md$/i.test(entry.name));
  const pages = await Promise.all(markdownFiles.map(async (entry) => {
    const source = await readFile(path.join(contentDir, entry.name), 'utf8');
    const parsed = matter(source);
    const slug = entry.name.replace(/\.md$/i, '');
    const title = typeof parsed.data.title === 'string' && parsed.data.title.trim() ? parsed.data.title : slug;
    return {
      slug,
      title,
      date: toDateString(parsed.data.date),
      tags: toTags(parsed.data.tags),
      html: await marked.parse(parsed.content),
      template: toTemplateName(parsed.data.template),
      layout: toTemplateName(parsed.data.layout),
      data: parsed.data
    };
  }));
  return pages.sort((left, right) => (right.date ?? '').localeCompare(left.date ?? ''));
}

async function renderPage(page: Page, templatesDir?: string): Promise<string> {
  if (!templatesDir) return pageDocument(page);
  const context = { ...page.data, ...page };
  const content = await renderTemplate(templatesDir, page.template ?? 'default', context);
  const layout = page.layout ?? 'default';
  return renderTemplate(path.join(templatesDir, 'layouts'), layout, { ...context, body: new Handlebars.SafeString(content) });
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? 'content');
  const outputDir = path.resolve(options.outputDir ?? 'dist');
  const templatesDir = path.resolve(options.templatesDir ?? 'templates');
  const pages = await readPages(contentDir);
  const hasTemplates = await directoryExists(templatesDir);
  if (hasTemplates) await loadPartials(templatesDir);
  await rm(outputDir, { recursive: true, force: true });
  await mkdir(outputDir, { recursive: true });
  await Promise.all(pages.map(async (page) => {
    await writeFile(path.join(outputDir, `${page.slug}.html`), await renderPage(page, hasTemplates ? templatesDir : undefined));
  }));
  await writeFile(path.join(outputDir, 'index.html'), indexDocument(pages));
  return pages;
}
