import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { relative, resolve, sep, extname } from 'node:path';
import matter from 'gray-matter';
import Handlebars from 'handlebars';
import { marked } from 'marked';

export interface Page {
  sourcePath: string;
  outputPath: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
}

interface PageData {
  title?: unknown;
  date?: unknown;
  tags?: unknown;
  template?: unknown;
  layout?: unknown;
  [key: string]: unknown;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  })[character]!);
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const paths = await Promise.all(entries.map(async (entry) => {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(path);
    return entry.isFile() && /\.md$/i.test(entry.name) ? [path] : [];
  }));
  return paths.flat();
}

async function templateFiles(directory: string): Promise<string[]> {
  try {
    const entries = await readdir(directory, { withFileTypes: true });
    const paths = await Promise.all(entries.map(async (entry) => {
      const path = resolve(directory, entry.name);
      if (entry.isDirectory()) return templateFiles(path);
      return entry.isFile() && extname(entry.name) === '.hbs' ? [path] : [];
    }));
    return paths.flat();
  } catch (error: unknown) {
    if (error instanceof Error && 'code' in error && error.code === 'ENOENT') return [];
    throw error;
  }
}

function outputPathFor(sourcePath: string, contentDir: string): string {
  const relativePath = relative(contentDir, sourcePath);
  return relativePath.replace(/\.md$/i, '.html');
}

function dateValue(value: unknown): string | undefined {
  if (value === undefined || value === null) return undefined;
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  return String(value);
}

function pageDocument(page: Page): string {
  const metadata = [
    page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '',
    page.tags.length ? `<p>Tags: ${page.tags.map(escapeHtml).join(', ')}</p>` : ''
  ].filter(Boolean).join('\n');

  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escapeHtml(page.title)}</title></head>
<body>
<main>
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

function indexDocument(pages: Page[]): string {
  const items = pages.map((page) => {
    const details = [page.date, page.tags.length ? page.tags.join(', ') : ''].filter(Boolean).join(' | ');
    const detailHtml = details ? ` <small>${escapeHtml(details)}</small>` : '';
    return `<li><a href="${encodeURI(page.outputPath.split(sep).join('/'))}">${escapeHtml(page.title)}</a>${detailHtml}</li>`;
  }).join('\n');
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Pages</title></head>
<body><main><h1>Pages</h1><ul>${items}</ul></main></body>
</html>
`;
}

function templatePath(templatesDir: string, directory: string, name: string): string {
  const filename = name.endsWith('.hbs') ? name : `${name}.hbs`;
  return resolve(templatesDir, directory, filename);
}

async function readTemplate(path: string): Promise<string | undefined> {
  try {
    return await readFile(path, 'utf8');
  } catch (error: unknown) {
    if (error instanceof Error && 'code' in error && error.code === 'ENOENT') return undefined;
    throw error;
  }
}

async function renderPage(
  page: Page,
  data: PageData,
  templatesDir: string
): Promise<string> {
  const engine = Handlebars.create();
  const partialsDir = resolve(templatesDir, 'partials');
  const partials = await templateFiles(partialsDir);
  await Promise.all(partials.map(async (path) => {
    const name = relative(partialsDir, path).replace(/\\/g, '/').replace(/\.hbs$/, '');
    engine.registerPartial(name, await readFile(path, 'utf8'));
  }));

  const templateName = typeof data.template === 'string' && data.template.trim()
    ? data.template
    : 'default';
  const template = await readTemplate(templatePath(templatesDir, '', templateName));
  if (!template) {
    if (templateName === 'default') return pageDocument(page);
    throw new Error(`Template not found: ${templateName}`);
  }

  const context = { ...data, ...page, content: page.html };
  let document = engine.compile(template)(context);
  const layoutName = typeof data.layout === 'string' && data.layout.trim()
    ? data.layout
    : 'default';
  const layout = await readTemplate(templatePath(templatesDir, 'layouts', layoutName));
  if (!layout) {
    if (layoutName === 'default') return document;
    throw new Error(`Layout not found: ${layoutName}`);
  }
  document = engine.compile(layout)({ ...context, body: new Handlebars.SafeString(document) });
  return document;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = resolve(options.contentDir ?? 'content');
  const outputDir = resolve(options.outputDir ?? 'dist');
  const templatesDir = resolve(options.templatesDir ?? 'templates');
  const files = await markdownFiles(contentDir);
  const sourcePages = await Promise.all(files.map(async (sourcePath) => {
    const parsed = matter(await readFile(sourcePath, 'utf8'));
    const data = parsed.data as PageData;
    const relativeOutput = outputPathFor(sourcePath, contentDir);
    const title = typeof data.title === 'string' && data.title.trim()
      ? data.title
      : relativeOutput.replace(/\.html$/i, '');
    const tags = Array.isArray(data.tags) ? data.tags.map(String) : [];
    const page: Page = {
      sourcePath,
      outputPath: relativeOutput,
      title,
      date: dateValue(data.date),
      tags,
      html: await marked.parse(parsed.content)
    };
    return { page, data };
  }));

  const pages = sourcePages.map(({ page }) => page);
  pages.sort((a, b) => a.title.localeCompare(b.title));
  await rm(outputDir, { recursive: true, force: true });
  await mkdir(outputDir, { recursive: true });
  await Promise.all(sourcePages.map(async ({ page, data }) => {
    const destination = resolve(outputDir, page.outputPath);
    await mkdir(resolve(destination, '..'), { recursive: true });
    await writeFile(destination, await renderPage(page, data, templatesDir));
  }));
  await writeFile(resolve(outputDir, 'index.html'), indexDocument(pages));
  return pages;
}
