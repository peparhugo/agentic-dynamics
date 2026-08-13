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
  sourcePath: string;
  outputPath: string;
  url: string;
  html: string;
  data: Record<string, unknown>;
}

interface TemplateEngine {
  renderPage(page: Page): string;
  renderIndex(pages: Page[]): string;
}

const escapeHtml = (value: string): string => value
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#39;');

function titleFromFilename(filename: string): string {
  const stem = path.basename(filename, path.extname(filename));
  return stem
    .replace(/[-_]+/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function parseDate(value: unknown): string | undefined {
  if (value instanceof Date) {
    return value.toISOString().slice(0, 10);
  }
  if (typeof value === 'string' || typeof value === 'number') {
    return String(value);
  }
  return undefined;
}

function parseTags(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map(String).map((tag) => tag.trim()).filter(Boolean);
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
  return files.flat().sort((left, right) => left.localeCompare(right));
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

function renderPageBody(page: Page): string {
  const metadata = [
    page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '',
    page.tags.length > 0
      ? `<ul class="tags">${page.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>`
      : ''
  ].filter(Boolean).join('\n');

  return `<main>
  <article>
    <header>
      <h1>${escapeHtml(page.title)}</h1>
      ${metadata}
    </header>
    ${page.html}
  </article>
</main>`;
}

function renderPage(page: Page): string {
  return document(page.title, renderPageBody(page));
}

function renderIndexBody(pages: Page[]): string {
  const items = pages.map((page) => {
    const date = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
    return `    <li><a href="${escapeHtml(page.url)}">${escapeHtml(page.title)}</a>${date}</li>`;
  }).join('\n');

  return `<main>
  <h1>Pages</h1>
  <ul>
${items}
  </ul>
</main>`;
}

function renderIndex(pages: Page[]): string {
  return document('Pages', renderIndexBody(pages));
}

async function hbsFiles(directory: string): Promise<string[]> {
  let entries;
  try {
    entries = await fs.readdir(directory, { withFileTypes: true });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      return [];
    }
    throw error;
  }

  const files = await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      return hbsFiles(entryPath);
    }
    return /\.hbs$/i.test(entry.name) ? [entryPath] : [];
  }));
  return files.flat().sort((left, right) => left.localeCompare(right));
}

function templateName(value: unknown, fallback: string): string {
  if (typeof value !== 'string' || !value.trim()) {
    return fallback;
  }
  const name = value.trim().replace(/\.hbs$/i, '');
  if (path.isAbsolute(name) || name.split(/[\\/]/).includes('..')) {
    throw new Error(`Invalid template name: ${value}`);
  }
  return name;
}

async function loadTemplateEngine(templatesDir: string): Promise<TemplateEngine> {
  const handlebars = Handlebars.create();
  const partialsDir = path.join(templatesDir, 'partials');
  const partialFiles = await hbsFiles(partialsDir);
  await Promise.all(partialFiles.map(async (filename) => {
    const relative = path.relative(partialsDir, filename).replace(/\.hbs$/i, '').split(path.sep).join('/');
    handlebars.registerPartial(relative, await fs.readFile(filename, 'utf8'));
  }));

  const templateFiles = (await hbsFiles(templatesDir)).filter((filename) => {
    const relative = path.relative(templatesDir, filename);
    return !relative.startsWith(`layouts${path.sep}`) && !relative.startsWith(`partials${path.sep}`);
  });
  const layoutFiles = await hbsFiles(path.join(templatesDir, 'layouts'));
  const templates = new Map<string, Handlebars.TemplateDelegate>();
  const layouts = new Map<string, Handlebars.TemplateDelegate>();

  await Promise.all(templateFiles.map(async (filename) => {
    const name = path.relative(templatesDir, filename).replace(/\.hbs$/i, '').split(path.sep).join('/');
    templates.set(name, handlebars.compile(await fs.readFile(filename, 'utf8')));
  }));
  await Promise.all(layoutFiles.map(async (filename) => {
    const name = path.relative(path.join(templatesDir, 'layouts'), filename)
      .replace(/\.hbs$/i, '').split(path.sep).join('/');
    layouts.set(name, handlebars.compile(await fs.readFile(filename, 'utf8')));
  }));

  const applyLayout = (body: string, context: Record<string, unknown>, requested: unknown): string => {
    const name = templateName(requested, 'default');
    const layout = layouts.get(name);
    if (!layout) {
      if (requested !== undefined && requested !== null && requested !== '') {
        throw new Error(`Layout not found: ${name}.hbs`);
      }
      return body;
    }
    return layout({ ...context, body });
  };

  return {
    renderPage(page): string {
      const name = templateName(page.data.template, 'default');
      const template = templates.get(name);
      if (!template) {
        if (page.data.template !== undefined) {
          throw new Error(`Template not found: ${name}.hbs`);
        }
        const context = { ...page.data, ...page, content: page.html };
        if (page.data.layout !== undefined || layouts.has('default')) {
          return applyLayout(renderPageBody(page), context, page.data.layout);
        }
        return renderPage(page);
      }
      const context = { ...page.data, ...page, content: page.html };
      return applyLayout(template(context), context, page.data.layout);
    },
    renderIndex(pages): string {
      const template = templates.get('index');
      const context = { title: 'Pages', pages };
      if (template) {
        return applyLayout(template(context), context, undefined);
      }
      return layouts.has('default')
        ? applyLayout(renderIndexBody(pages), context, undefined)
        : renderIndex(pages);
    }
  };
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? 'content');
  const outputDir = path.resolve(options.outputDir ?? 'dist');
  const templatesDir = path.resolve(options.templatesDir ?? 'templates');

  let files: string[];
  try {
    files = await markdownFiles(contentDir);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      throw new Error(`Content directory does not exist: ${contentDir}`);
    }
    throw error;
  }

  const pages = await Promise.all(files.map(async (sourcePath): Promise<Page> => {
    const relativePath = path.relative(contentDir, sourcePath);
    const parsed = matter(await fs.readFile(sourcePath, 'utf8'));
    const outputRelativePath = relativePath.replace(/\.md$/i, '.html');
    const title = typeof parsed.data.title === 'string' && parsed.data.title.trim()
      ? parsed.data.title.trim()
      : titleFromFilename(sourcePath);

    return {
      title,
      date: parseDate(parsed.data.date),
      tags: parseTags(parsed.data.tags),
      sourcePath,
      outputPath: path.join(outputDir, outputRelativePath),
      url: outputRelativePath.split(path.sep).map(encodeURIComponent).join('/'),
      html: await marked.parse(parsed.content),
      data: parsed.data
    };
  }));

  pages.sort((left, right) => {
    if (left.date && right.date && left.date !== right.date) {
      return right.date.localeCompare(left.date);
    }
    return left.title.localeCompare(right.title);
  });

  const templates = await loadTemplateEngine(templatesDir);
  await fs.mkdir(outputDir, { recursive: true });
  await Promise.all(pages.map(async (page) => {
    await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
    await fs.writeFile(page.outputPath, templates.renderPage(page), 'utf8');
  }));
  await fs.writeFile(path.join(outputDir, 'index.html'), templates.renderIndex(pages), 'utf8');

  return pages;
}
