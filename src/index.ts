import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import Handlebars from 'handlebars';
import { marked } from 'marked';

export interface Frontmatter {
  title?: string;
  date?: string | Date;
  tags?: string[] | string;
  template?: string;
  layout?: string;
  [key: string]: unknown;
}

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  url: string;
  html: string;
  data?: Frontmatter;
  template?: string;
  layout?: string;
}

export interface BuildOptions {
  content?: string;
  output?: string;
  templates?: string;
}

type TemplateContext = Record<string, unknown>;

interface TemplateEngine {
  compile(source: string): (context: TemplateContext) => string;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(fullPath);
    return /\.md$/i.test(entry.name) ? [fullPath] : [];
  }));
  return files.flat().sort();
}

function normalizeDate(value: unknown): string | undefined {
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === 'string' && value.trim()) return value.trim();
  return undefined;
}

function normalizeTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String).map((tag) => tag.trim()).filter(Boolean);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

function defaultLayout(title: string, body: string): string {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)}</title>
</head>
<body>
${body}
</body>
</html>
`;
}

function defaultPage(page: Page): string {
  const metadata = [
    page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '',
    ...page.tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`),
  ].filter(Boolean).join(' ');
  return `<main>
  <article>
    <header><h1>${escapeHtml(page.title)}</h1>${metadata ? `\n    <p>${metadata}</p>` : ''}</header>
    ${page.html}
  </article>
</main>`;
}

function renderIndex(pages: Page[]): string {
  const items = pages.map((page) => {
    const date = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
    return `    <li><a href="${escapeHtml(page.url)}">${escapeHtml(page.title)}</a>${date}</li>`;
  }).join('\n');
  return defaultLayout('Pages', `<main>
  <h1>Pages</h1>
  <ul>
${items}
  </ul>
</main>`);
}

async function isFile(file: string): Promise<boolean> {
  try {
    return (await fs.stat(file)).isFile();
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return false;
    throw error;
  }
}

function templateName(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

function templatePath(directory: string, name: string): string {
  const normalized = name.endsWith('.hbs') ? name : `${name}.hbs`;
  const root = path.resolve(directory);
  const resolved = path.resolve(root, normalized);
  if (resolved !== root && !resolved.startsWith(`${root}${path.sep}`)) {
    throw new Error(`Template path must stay inside ${directory}: ${name}`);
  }
  return resolved;
}

async function loadPartials(directory: string): Promise<Record<string, string>> {
  const partials: Record<string, string> = {};
  let files: string[];
  try {
    files = await templateFiles(directory);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return partials;
    throw error;
  }
  await Promise.all(files.map(async (file) => {
    const name = path.relative(directory, file).replace(/\.hbs$/i, '').split(path.sep).join('/');
    partials[name] = await fs.readFile(file, 'utf8');
  }));
  return partials;
}

async function templateFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return templateFiles(fullPath);
    return /\.hbs$/i.test(entry.name) ? [fullPath] : [];
  }));
  return files.flat().sort();
}

async function renderPage(page: Page, templatesDirectory: string, engine: TemplateEngine): Promise<string> {
  const context: TemplateContext = { ...(page.data ?? {}), ...page, content: page.html };
  const selectedTemplate = page.template ?? 'default';
  const selectedTemplatePath = templatePath(templatesDirectory, selectedTemplate);
  const body = await isFile(selectedTemplatePath)
    ? engine.compile(await fs.readFile(selectedTemplatePath, 'utf8'))(context)
    : page.template
      ? (() => { throw new Error(`Template not found: ${selectedTemplate}`); })()
      : defaultPage(page);

  const selectedLayout = page.layout ?? 'default';
  const selectedLayoutPath = templatePath(path.join(templatesDirectory, 'layouts'), selectedLayout);
  if (await isFile(selectedLayoutPath)) {
    return engine.compile(await fs.readFile(selectedLayoutPath, 'utf8'))({ ...context, body });
  }
  if (page.layout) throw new Error(`Layout not found: ${selectedLayout}`);
  return defaultLayout(page.title, body);
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDirectory = path.resolve(options.content ?? './content');
  const outputDirectory = path.resolve(options.output ?? './dist');
  const templatesDirectory = path.resolve(options.templates ?? './templates');
  if (contentDirectory === outputDirectory) {
    throw new Error('Content and output directories must be different');
  }
  const files = await markdownFiles(contentDirectory);

  const pages = await Promise.all(files.map(async (file): Promise<Page> => {
    const source = await fs.readFile(file, 'utf8');
    const parsed = matter(source);
    const frontmatter = parsed.data as Frontmatter;
    const relativePath = path.relative(contentDirectory, file);
    const url = relativePath.replace(/\.md$/i, '.html').split(path.sep).join('/');
    const fallbackTitle = path.basename(file, path.extname(file));
    return {
      title: typeof frontmatter.title === 'string' && frontmatter.title.trim()
        ? frontmatter.title.trim()
        : fallbackTitle,
      date: normalizeDate(frontmatter.date),
      tags: normalizeTags(frontmatter.tags),
      url,
      html: await marked.parse(parsed.content),
      data: frontmatter,
      template: templateName(frontmatter.template),
      layout: templateName(frontmatter.layout),
    };
  }));

  pages.sort((left, right) => {
    if (left.date && right.date && left.date !== right.date) return right.date.localeCompare(left.date);
    if (left.date !== right.date) return left.date ? -1 : 1;
    return left.title.localeCompare(right.title);
  });

  await fs.rm(outputDirectory, { recursive: true, force: true });
  await fs.mkdir(outputDirectory, { recursive: true });
  const engine = Handlebars.create();
  engine.registerPartial(await loadPartials(path.join(templatesDirectory, 'partials')));
  await Promise.all(pages.map(async (page) => {
    const destination = path.join(outputDirectory, ...page.url.split('/'));
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, await renderPage(page, templatesDirectory, engine), 'utf8');
  }));
  await fs.writeFile(path.join(outputDirectory, 'index.html'), renderIndex(pages), 'utf8');
  return pages;
}
