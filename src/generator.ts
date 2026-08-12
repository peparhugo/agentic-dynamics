import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import Handlebars from 'handlebars';
import { BuildOptions, Frontmatter, Page } from './types';

const DEFAULT_CONTENT_DIR = './content';
const DEFAULT_OUTPUT_DIR = './dist';
const DEFAULT_TEMPLATES_DIR = './templates';

function asString(value: unknown): string | undefined {
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  return undefined;
}

function normalizeTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

function normalizeFrontmatter(data: Record<string, unknown>, fallbackTitle: string): Frontmatter {
  const frontmatter: Frontmatter = {
    title: asString(data.title) || fallbackTitle,
    date: asString(data.date),
    tags: normalizeTags(data.tags),
  };
  const template = asString(data.template);
  const layout = asString(data.layout);
  if (template) frontmatter.template = template;
  if (layout) frontmatter.layout = layout;
  return frontmatter;
}

function titleFromFilename(filePath: string): string {
  return path.basename(filePath, path.extname(filePath)).replace(/[-_]+/g, ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(entryPath));
    else if (entry.isFile() && /\.md$/i.test(entry.name)) files.push(entryPath);
  }
  return files.sort((a, b) => a.localeCompare(b));
}

export async function parseMarkdown(sourcePath: string, content: string, contentDir?: string): Promise<Page> {
  const parsed = matter(content);
  const relativePath = contentDir ? path.relative(contentDir, sourcePath) : path.basename(sourcePath);
  const slug = relativePath.replace(/\\/g, '/').replace(/\.md$/i, '');
  const frontmatter = normalizeFrontmatter(parsed.data as Record<string, unknown>, titleFromFilename(sourcePath));
  return {
    sourcePath,
    outputPath: `${slug}.html`,
    slug,
    frontmatter,
    html: await marked.parse(parsed.content),
  };
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character] as string));
}

function pageDocument(page: Page): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>${escapeHtml(page.frontmatter.title)}</title>\n</head>\n<body>\n<main>\n<h1>${escapeHtml(page.frontmatter.title)}</h1>\n${page.frontmatter.date ? `<time datetime="${escapeHtml(page.frontmatter.date)}">${escapeHtml(page.frontmatter.date)}</time>\n` : ''}${page.html}</main>\n</body>\n</html>\n`;
}

function indexDocument(pages: Page[]): string {
  const items = pages.map((page) => {
    const metadata = [page.frontmatter.date, ...page.frontmatter.tags].filter(Boolean).map(escapeHtml).join(' | ');
    return `<li><a href="${encodeURI(page.outputPath)}">${escapeHtml(page.frontmatter.title)}</a>${metadata ? ` <small>${metadata}</small>` : ''}</li>`;
  }).join('\n');
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>Home</title>\n</head>\n<body>\n<main>\n<h1>Pages</h1>\n<ul>\n${items}\n</ul>\n</main>\n</body>\n</html>\n`;
}

async function templatePath(directory: string, name: string): Promise<string | undefined> {
  const requested = path.extname(name) ? [name] : [`${name}.hbs`, `${name}.handlebars`];
  for (const candidate of requested) {
    const filePath = path.join(directory, candidate);
    try {
      if ((await fs.stat(filePath)).isFile()) return filePath;
    } catch {
      // Try the next supported template extension.
    }
  }
  return undefined;
}

async function registerPartials(
  handlebars: { registerPartial: (name: string, template: string) => void },
  directory: string,
  prefix = '',
): Promise<void> {
  let entries: import('node:fs').Dirent[];
  try {
    entries = await fs.readdir(directory, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      await registerPartials(handlebars, entryPath, `${prefix}${entry.name}/`);
    } else if (entry.isFile() && /\.(hbs|handlebars)$/i.test(entry.name)) {
      const name = `${prefix}${entry.name}`.replace(/\.(hbs|handlebars)$/i, '');
      handlebars.registerPartial(name, await fs.readFile(entryPath, 'utf8'));
    }
  }
}

async function renderWithTemplates(page: Page, templatesDir: string): Promise<string | undefined> {
  const templateName = page.frontmatter.template || 'default';
  const templateFile = await templatePath(templatesDir, templateName);
  if (!templateFile) return undefined;

  const handlebars = Handlebars.create();
  await registerPartials(handlebars, path.join(templatesDir, 'partials'));
  const context = {
    ...page.frontmatter,
    frontmatter: page.frontmatter,
    page,
    content: page.html,
    body: page.html,
  };
  let output = handlebars.compile(await fs.readFile(templateFile, 'utf8'))(context);
  if (page.frontmatter.layout) {
    const layoutFile = await templatePath(path.join(templatesDir, 'layouts'), page.frontmatter.layout);
    if (!layoutFile) throw new Error(`Layout template not found: ${page.frontmatter.layout}`);
    output = handlebars.compile(await fs.readFile(layoutFile, 'utf8'))({ ...context, body: output });
  }
  return output;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir || DEFAULT_CONTENT_DIR);
  const outputDir = path.resolve(options.outputDir || DEFAULT_OUTPUT_DIR);
  const templatesDir = path.resolve(options.templatesDir || DEFAULT_TEMPLATES_DIR);
  const files = await markdownFiles(contentDir);
  const pages = await Promise.all(files.map(async (file) => parseMarkdown(file, await fs.readFile(file, 'utf8'), contentDir)));
  pages.sort((a, b) => a.slug.localeCompare(b.slug));
  await fs.mkdir(outputDir, { recursive: true });
  await Promise.all(pages.map(async (page) => {
    const destination = path.join(outputDir, page.outputPath);
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, (await renderWithTemplates(page, templatesDir)) || pageDocument(page), 'utf8');
  }));
  await fs.writeFile(path.join(outputDir, 'index.html'), indexDocument(pages), 'utf8');
  return pages;
}

export { escapeHtml, indexDocument, pageDocument };
