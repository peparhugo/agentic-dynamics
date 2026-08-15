import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { basename, extname, join, relative } from 'node:path';
import matter from 'gray-matter';
import Handlebars from 'handlebars';
import { marked } from 'marked';

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  slug: string;
  html: string;
  template?: string;
  layout?: string;
}

type Frontmatter = Record<string, string | string[]>;

/** Parse the deliberately small YAML subset supported by this generator. */
function parseYaml(block: string): Frontmatter {
  const data: Frontmatter = {};
  for (const line of block.split(/\r?\n/)) {
    const match = line.match(/^([\w-]+):\s*(.*)$/);
    if (!match) continue;
    const [, key, rawValue] = match;
    const value = rawValue.trim().replace(/^(["'])(.*)\1$/, '$2');
    data[key] = value.startsWith('[') && value.endsWith(']')
      ? value.slice(1, -1).split(',').map((tag) => tag.trim().replace(/^(["'])(.*)\1$/, '$2')).filter(Boolean)
      : value;
  }
  return data;
}

function extractYaml(source: string): Frontmatter {
  const match = source.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
  return match ? parseYaml(match[1]) : {};
}

export function parsePage(source: string, filePath: string): Page {
  const parsed = matter(source);
  // Merge the required lightweight YAML parser over gray-matter's data.
  const data = { ...parsed.data, ...extractYaml(source) } as Frontmatter;
  const name = basename(filePath, extname(filePath));
  const tags = data.tags === undefined ? [] : Array.isArray(data.tags)
    ? data.tags
    : data.tags.split(',').map((tag) => tag.trim()).filter(Boolean);

  return {
    title: typeof data.title === 'string' ? data.title : name,
    date: typeof data.date === 'string' ? data.date : undefined,
    tags,
    slug: name,
    html: marked.parse(parsed.content) as string,
    template: typeof data.template === 'string' ? data.template : undefined,
    layout: typeof data.layout === 'string' ? data.layout : undefined,
  };
}

function markdownFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(path);
    return entry.isFile() && ['.md', '.markdown'].includes(extname(entry.name).toLowerCase()) ? [path] : [];
  });
}

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function document(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escapeHtml(title)}</title></head>\n<body>\n${body}\n</body>\n</html>\n`;
}

function renderPage(page: Page): string {
  const metadata = [page.date, page.tags.length ? page.tags.join(', ') : undefined].filter(Boolean).join(' | ');
  return document(page.title, `<article>\n<h1>${escapeHtml(page.title)}</h1>${metadata ? `\n<p>${escapeHtml(metadata)}</p>` : ''}\n${page.html}</article>`);
}

function hbsFile(directory: string, name: string): string {
  return join(directory, `${name.endsWith('.hbs') ? name : `${name}.hbs`}`);
}

function registerPartials(partialsDir: string): void {
  if (!existsSync(partialsDir)) return;
  for (const path of hbsFiles(partialsDir)) {
    const name = relative(partialsDir, path).replace(/\\/g, '/').replace(/\.hbs$/i, '');
    Handlebars.registerPartial(name, readFileSync(path, 'utf8'));
  }
}

function hbsFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return hbsFiles(path);
    return entry.isFile() && extname(entry.name).toLowerCase() === '.hbs' ? [path] : [];
  });
}

function renderTemplate(path: string, context: Page & { body?: string; content?: string }): string {
  return Handlebars.compile(readFileSync(path, 'utf8'))(context);
}

function renderTemplatedPage(page: Page, templatesDir: string): string {
  const templatePath = hbsFile(templatesDir, page.template ?? 'default');
  if (!existsSync(templatePath)) {
    if (!page.template) return renderPage(page);
    throw new Error(`Template does not exist: ${templatePath}`);
  }

  const body = renderTemplate(templatePath, { ...page, content: page.html });
  const layoutPath = hbsFile(join(templatesDir, 'layouts'), page.layout ?? 'default');
  if (!existsSync(layoutPath)) {
    if (!page.layout) return body;
    throw new Error(`Layout does not exist: ${layoutPath}`);
  }
  return renderTemplate(layoutPath, { ...page, body, content: page.html });
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
}

export function buildSite({ contentDir = './content', outputDir = './dist', templatesDir = './templates' }: BuildOptions = {}): Page[] {
  if (!existsSync(contentDir)) throw new Error(`Content directory does not exist: ${contentDir}`);
  rmSync(outputDir, { recursive: true, force: true });
  mkdirSync(outputDir, { recursive: true });
  Handlebars.partials = {};
  registerPartials(join(templatesDir, 'partials'));

  const pages = markdownFiles(contentDir).map((path) => {
    const page = parsePage(readFileSync(path, 'utf8'), path);
    const relativePath = relative(contentDir, path).replace(/\.(md|markdown)$/i, '');
    page.slug = relativePath.replace(/\\/g, '/');
    const outputPath = join(outputDir, `${relativePath}.html`);
    mkdirSync(join(outputPath, '..'), { recursive: true });
    writeFileSync(outputPath, renderTemplatedPage(page, templatesDir));
    return page;
  }).sort((a, b) => (b.date ?? '').localeCompare(a.date ?? ''));

  const links = pages.map((page) => `<li><a href="${escapeHtml(`${page.slug}.html`)}">${escapeHtml(page.title)}</a>${page.date ? ` <time>${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n');
  writeFileSync(join(outputDir, 'index.html'), document('Index', `<main>\n<h1>Pages</h1>\n<ul>\n${links}\n</ul>\n</main>`));
  return pages;
}
