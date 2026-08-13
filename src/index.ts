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

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  outputPath: string;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function formatDate(value: unknown): string | undefined {
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    return value.toISOString().slice(0, 10);
  }
  if (typeof value === 'string' || typeof value === 'number') {
    return String(value);
  }
  return undefined;
}

function formatTags(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map(String);
  }
  if (typeof value === 'string') {
    return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  }
  return [];
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      return markdownFiles(entryPath);
    }
    return /\.md$/i.test(entry.name) ? [entryPath] : [];
  }));
  return files.flat().sort();
}

async function exists(file: string): Promise<boolean> {
  try {
    await fs.access(file);
    return true;
  } catch {
    return false;
  }
}

async function templateFiles(directory: string): Promise<string[]> {
  if (!await exists(directory)) {
    return [];
  }
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      return templateFiles(entryPath);
    }
    return /\.hbs$/i.test(entry.name) ? [entryPath] : [];
  }));
  return files.flat().sort();
}

function namedTemplate(directory: string, value: unknown, field: string): string | undefined {
  if (typeof value !== 'string' || value.trim() === '') {
    return undefined;
  }
  const name = value.trim().replace(/\.hbs$/i, '') + '.hbs';
  const file = path.resolve(directory, name);
  const relative = path.relative(directory, file);
  if (relative.startsWith('..' + path.sep) || path.isAbsolute(relative)) {
    throw new Error(`${field} must be inside ${directory}`);
  }
  return file;
}

async function renderTemplate(file: string, context: Record<string, unknown>, engine: typeof Handlebars): Promise<string> {
  if (!await exists(file)) {
    throw new Error(`Template not found: ${file}`);
  }
  return engine.compile(await fs.readFile(file, 'utf8'))(context);
}

async function createTemplateEngine(partialsDir: string): Promise<typeof Handlebars> {
  const engine = Handlebars.create() as typeof Handlebars;
  for (const file of await templateFiles(partialsDir)) {
    const name = path.relative(partialsDir, file).replace(/\.hbs$/i, '').split(path.sep).join('/');
    engine.registerPartial(name, await fs.readFile(file, 'utf8'));
  }
  return engine;
}

function document(title: string, body: string): string {
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

function pageDocument(page: Page, content: string): string {
  const metadata = [
    page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '',
    page.tags.length > 0
      ? `<ul class="tags">${page.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>`
      : ''
  ].filter(Boolean).join('\n');

  return document(page.title, `<article>
  <header>
    <h1>${escapeHtml(page.title)}</h1>
    ${metadata}
  </header>
  ${content}
</article>`);
}

function indexDocument(pages: Page[]): string {
  const items = pages.map((page) => {
    const date = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
    const href = page.outputPath.split(path.sep).map(encodeURIComponent).join('/');
    return `<li><a href="${href}">${escapeHtml(page.title)}</a>${date}</li>`;
  }).join('\n    ');

  return document('Pages', `<main>
  <h1>Pages</h1>
  <ul>
    ${items}
  </ul>
</main>`);
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const files = await markdownFiles(contentDir);
  const engine = await createTemplateEngine(path.join(templatesDir, 'partials'));
  const defaultTemplate = path.join(templatesDir, 'default.hbs');
  const defaultLayout = path.join(templatesDir, 'layouts', 'default.hbs');

  await fs.mkdir(outputDir, { recursive: true });

  const pages = await Promise.all(files.map(async (file): Promise<Page> => {
    const source = await fs.readFile(file, 'utf8');
    const parsed = matter(source);
    const relativePath = path.relative(contentDir, file).replace(/\.md$/i, '.html');
    const fallbackTitle = path.basename(file, path.extname(file));
    const page: Page = {
      title: typeof parsed.data.title === 'string' ? parsed.data.title : fallbackTitle,
      date: formatDate(parsed.data.date),
      tags: formatTags(parsed.data.tags),
      outputPath: relativePath
    };
    const destination = path.join(outputDir, relativePath);

    const content = await marked.parse(parsed.content);
    const context: Record<string, unknown> = {
      ...parsed.data,
      ...page,
      content,
      body: content
    };
    const selectedTemplate = namedTemplate(templatesDir, parsed.data.template, 'template');
    let html: string;
    if (selectedTemplate) {
      html = await renderTemplate(selectedTemplate, context, engine);
    } else if (await exists(defaultTemplate)) {
      html = await renderTemplate(defaultTemplate, context, engine);
    } else {
      html = pageDocument(page, content);
    }

    const selectedLayout = namedTemplate(path.join(templatesDir, 'layouts'), parsed.data.layout, 'layout');
    const layout = selectedLayout ?? (await exists(defaultLayout) ? defaultLayout : undefined);
    if (layout) {
      html = await renderTemplate(layout, { ...context, body: html }, engine);
    }

    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, html, 'utf8');
    return page;
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

  await fs.writeFile(path.join(outputDir, 'index.html'), indexDocument(pages), 'utf8');
  return pages;
}

export { startDevServer, type DevServer, type ServeOptions } from './server';
