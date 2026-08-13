import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import Handlebars from 'handlebars';
import { marked } from 'marked';

type TemplateEngine = ReturnType<typeof Handlebars.create>;

export interface Page {
  sourcePath: string;
  outputPath: string;
  url: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  template?: string;
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
    "'": '&#39;',
  })[character] ?? character);
}

function valueToString(value: unknown): string | undefined {
  if (value === undefined || value === null) return undefined;
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  return String(value);
}

function toTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

async function filesIn(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return filesIn(fullPath);
    return [fullPath];
  }));
  return files.flat();
}

async function markdownFiles(directory: string): Promise<string[]> {
  return (await filesIn(directory)).filter((filePath) => /\.md$/i.test(filePath));
}

async function readTemplate(filePath: string): Promise<string | undefined> {
  try {
    return await fs.readFile(filePath, 'utf8');
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return undefined;
    throw error;
  }
}

async function registerPartials(engine: TemplateEngine, templatesDir: string): Promise<void> {
  const partialsDir = path.join(templatesDir, 'partials');
  let entries: string[];
  try {
    entries = await filesIn(partialsDir);
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return;
    throw error;
  }
  await Promise.all(entries.map(async (partialPath) => {
    const extension = path.extname(partialPath);
    if (extension !== '.hbs') return;
    const name = path.relative(partialsDir, partialPath).slice(0, -extension.length).split(path.sep).join('/');
    engine.registerPartial(name, await fs.readFile(partialPath, 'utf8'));
  }));
}

async function renderTemplate(engine: TemplateEngine, page: Page, templatesDir: string): Promise<string | undefined> {
  const templateName = page.template ?? 'default';
  const template = await readTemplate(path.join(templatesDir, `${templateName}.hbs`));
  if (template === undefined) return undefined;

  const content = engine.compile(template)({ ...page, body: page.html });
  const layout = await readTemplate(path.join(templatesDir, 'layouts', `${templateName}.hbs`))
    ?? await readTemplate(path.join(templatesDir, 'layouts', 'default.hbs'));
  return layout === undefined ? content : engine.compile(layout)({ ...page, body: content });
}

export function renderPage(page: Page): string {
  const details = [
    page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '',
    page.tags.length ? `<p class="tags">${page.tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join(' ')}</p>` : '',
  ].filter(Boolean).join('\n');

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(page.title)}</title>
</head>
<body>
  <main>
    <a href="/index.html">Home</a>
    <article>
      <h1>${escapeHtml(page.title)}</h1>
      ${details}
      ${page.html}
    </article>
  </main>
</body>
</html>
`;
}

export function renderIndex(pages: Page[]): string {
  const items = pages.map((page) => {
    const date = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
    return `      <li><a href="${escapeHtml(page.url)}">${escapeHtml(page.title)}</a>${date}</li>`;
  }).join('\n');
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Index</title>
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

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const templateEngine = Handlebars.create();
  await registerPartials(templateEngine, templatesDir);
  const files = await markdownFiles(contentDir);
  const pages = await Promise.all(files.map(async (sourcePath) => {
    const parsed = matter(await fs.readFile(sourcePath, 'utf8'));
    const relativePath = path.relative(contentDir, sourcePath);
    const outputPath = path.join(outputDir, relativePath.replace(/\.md$/i, '.html'));
    const fallbackTitle = path.basename(relativePath, path.extname(relativePath));
    const title = valueToString(parsed.data.title) ?? fallbackTitle;
    const date = valueToString(parsed.data.date);
    return {
      sourcePath,
      outputPath,
      url: `/${path.relative(outputDir, outputPath).split(path.sep).join('/')}`,
      title,
      date,
      tags: toTags(parsed.data.tags),
      html: await marked.parse(parsed.content),
      template: valueToString(parsed.data.template),
    };
  }));

  pages.sort((left, right) => (right.date ?? '').localeCompare(left.date ?? '') || left.title.localeCompare(right.title));
  await fs.rm(outputDir, { recursive: true, force: true });
  await fs.mkdir(outputDir, { recursive: true });
  await Promise.all(pages.map(async (page) => {
    await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
    await fs.writeFile(page.outputPath, await renderTemplate(templateEngine, page, templatesDir) ?? renderPage(page), 'utf8');
  }));
  await fs.writeFile(path.join(outputDir, 'index.html'), renderIndex(pages), 'utf8');
  return pages;
}
