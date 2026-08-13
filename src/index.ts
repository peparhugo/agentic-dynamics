import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import Handlebars from 'handlebars';
import { marked } from 'marked';

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
}

export interface GeneratedPage {
  title: string;
  date?: string;
  tags: string[];
  sourcePath: string;
  outputPath: string;
  url: string;
}

interface ParsedPage extends GeneratedPage {
  html: string;
  frontmatter: Record<string, unknown>;
  template?: string;
  layout?: string;
}

const DEFAULT_CONTENT_DIR = './content';
const DEFAULT_OUTPUT_DIR = './dist';
const DEFAULT_TEMPLATES_DIR = './templates';

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function normalizeDate(value: unknown): string | undefined {
  if (value instanceof Date) {
    return value.toISOString().slice(0, 10);
  }
  if (typeof value === 'string' || typeof value === 'number') {
    return String(value);
  }
  return undefined;
}

function normalizeTags(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map(String);
  }
  if (typeof value === 'string') {
    return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  }
  return [];
}

async function findMarkdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      return findMarkdownFiles(entryPath);
    }
    return /\.md$/i.test(entry.name) ? [entryPath] : [];
  }));
  return files.flat().sort();
}

function pageTemplate(page: ParsedPage): string {
  const title = escapeHtml(page.title);
  const depth = page.url.split('/').length - 1;
  const homeUrl = `${'../'.repeat(depth)}index.html`;
  const metadata = [
    page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '',
    page.tags.length > 0
      ? `<ul class="tags">${page.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>`
      : '',
  ].filter(Boolean).join('\n');

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${title}</title>
</head>
<body>
  <nav><a href="${homeUrl}">Home</a></nav>
  <main>
    <article>
      <header><h1>${title}</h1>${metadata ? `\n${metadata}` : ''}</header>
      ${page.html}
    </article>
  </main>
</body>
</html>
`;
}

function indexTemplate(pages: ParsedPage[]): string {
  const items = pages.map((page) => {
    const date = page.date
      ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>`
      : '';
    return `<li><a href="${escapeHtml(page.url)}">${escapeHtml(page.title)}</a>${date}</li>`;
  }).join('\n      ');

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pages</title>
</head>
<body>
  <main>
    <h1>Pages</h1>
    <ul>
      ${items}
    </ul>
  </main>
</body>
</html>
`;
}

async function isDirectory(directory: string): Promise<boolean> {
  try {
    return (await fs.stat(directory)).isDirectory();
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return false;
    throw error;
  }
}

async function findTemplateFile(directory: string, name: string): Promise<string> {
  const requested = path.resolve(directory, name.endsWith('.hbs') ? name : `${name}.hbs`);
  const relative = path.relative(directory, requested);
  if (relative.startsWith('..') || path.isAbsolute(relative)) {
    throw new Error(`Template must be inside ${directory}: ${name}`);
  }
  try {
    if ((await fs.stat(requested)).isFile()) return requested;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
  }
  throw new Error(`Template not found: ${name}`);
}

async function registerPartials(handlebars: typeof Handlebars, partialsDir: string): Promise<void> {
  if (!await isDirectory(partialsDir)) return;
  const files = await findHandlebarsFiles(partialsDir);
  await Promise.all(files.map(async (file) => {
    const relative = path.relative(partialsDir, file).replace(/\.hbs$/i, '').split(path.sep).join('/');
    handlebars.registerPartial(relative, await fs.readFile(file, 'utf8'));
  }));
}

async function findHandlebarsFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return findHandlebarsFiles(entryPath);
    return /\.hbs$/i.test(entry.name) ? [entryPath] : [];
  }));
  return files.flat().sort();
}

async function renderPage(page: ParsedPage, templatesDir: string, handlebars: typeof Handlebars): Promise<string> {
  const defaultTemplate = path.join(templatesDir, 'default.hbs');
  const hasDefaultTemplate = await fs.stat(defaultTemplate).then((stat) => stat.isFile()).catch(() => false);
  if (!page.template && !hasDefaultTemplate && !page.layout) return pageTemplate(page);

  const context = {
    ...page.frontmatter,
    title: page.title,
    date: page.date,
    tags: page.tags,
    url: page.url,
    content: new handlebars.SafeString(page.html),
  };
  let rendered = page.template || hasDefaultTemplate
    ? handlebars.compile(await fs.readFile(
      page.template ? await findTemplateFile(templatesDir, page.template) : defaultTemplate,
      'utf8',
    ))(context)
    : page.html;

  if (page.layout) {
    const layoutPath = await findTemplateFile(path.join(templatesDir, 'layouts'), page.layout);
    rendered = handlebars.compile(await fs.readFile(layoutPath, 'utf8'))({
      ...context,
      body: new handlebars.SafeString(rendered),
    });
  }
  return rendered;
}

export async function buildSite(options: BuildOptions = {}): Promise<GeneratedPage[]> {
  const contentDir = path.resolve(options.contentDir ?? DEFAULT_CONTENT_DIR);
  const outputDir = path.resolve(options.outputDir ?? DEFAULT_OUTPUT_DIR);
  const templatesDir = path.resolve(options.templatesDir ?? DEFAULT_TEMPLATES_DIR);
  const files = await findMarkdownFiles(contentDir);

  const pages = await Promise.all(files.map(async (sourcePath): Promise<ParsedPage> => {
    const source = await fs.readFile(sourcePath, 'utf8');
    const parsed = matter(source);
    const relativePath = path.relative(contentDir, sourcePath);
    const relativeOutput = relativePath.replace(/\.md$/i, '.html');
    const title = typeof parsed.data.title === 'string'
      ? parsed.data.title
      : path.basename(relativePath, path.extname(relativePath));

    return {
      title,
      date: normalizeDate(parsed.data.date),
      tags: normalizeTags(parsed.data.tags),
      sourcePath,
      outputPath: path.join(outputDir, relativeOutput),
      url: relativeOutput.split(path.sep).join('/'),
      html: await marked.parse(parsed.content),
      frontmatter: parsed.data,
      template: typeof parsed.data.template === 'string' ? parsed.data.template : undefined,
      layout: typeof parsed.data.layout === 'string' ? parsed.data.layout : undefined,
    };
  }));

  pages.sort((left, right) => {
    if (left.date && right.date && left.date !== right.date) {
      return right.date.localeCompare(left.date);
    }
    if (left.date !== right.date) {
      return left.date ? -1 : 1;
    }
    return left.title.localeCompare(right.title);
  });

  await fs.rm(outputDir, { recursive: true, force: true });
  const handlebars = Handlebars.create();
  await registerPartials(handlebars, path.join(templatesDir, 'partials'));
  await Promise.all(pages.map(async (page) => {
    await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
    await fs.writeFile(page.outputPath, await renderPage(page, templatesDir, handlebars), 'utf8');
  }));
  await fs.mkdir(outputDir, { recursive: true });
  await fs.writeFile(path.join(outputDir, 'index.html'), indexTemplate(pages), 'utf8');

  return pages.map(({ html: _html, frontmatter: _frontmatter, template: _template, layout: _layout, ...page }) => page);
}

export { serveSite, type DevServer, type ServeOptions } from './server';
