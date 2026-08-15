import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { basename, join, relative, resolve, sep } from 'node:path';
import matter from 'gray-matter';
import Handlebars from 'handlebars';
import MarkdownIt from 'markdown-it';

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  slug: string;
  html: string;
  template?: string;
  layout?: string;
  frontmatter: Record<string, unknown>;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templateDir?: string;
}

type Frontmatter = Record<string, string | string[]>;

const markdown = new MarkdownIt({ html: true });

function parseYamlFrontmatter(source: string): Frontmatter {
  const match = source.match(/^---\s*\r?\n([\s\S]*?)\r?\n---\s*(?:\r?\n|$)/);
  if (!match) return {};

  return match[1].split(/\r?\n/).reduce<Frontmatter>((data, line) => {
    const separator = line.indexOf(':');
    if (separator === -1) return data;

    const key = line.slice(0, separator).trim();
    const value = line.slice(separator + 1).trim();
    if (!key) return data;

    const unquoted = value.replace(/^(?:"|')|(?:"|')$/g, '');
    data[key] = unquoted.startsWith('[') && unquoted.endsWith(']')
      ? unquoted.slice(1, -1).split(',').map((tag) => tag.trim().replace(/^(?:"|')|(?:"|')$/g, '')).filter(Boolean)
      : unquoted;
    return data;
  }, {});
}

function stringValue(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

function tagValues(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((tag): tag is string => typeof tag === 'string');
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

export function parsePage(source: string, filename: string): Page {
  const parsed = matter(source);
  const data = { ...parsed.data, ...parseYamlFrontmatter(source) };
  const fallbackTitle = basename(filename, '.md').replace(/[-_]/g, ' ');

  return {
    title: stringValue(data.title) ?? fallbackTitle,
    date: stringValue(data.date),
    tags: tagValues(data.tags),
    slug: basename(filename, '.md'),
    html: markdown.render(parsed.content),
    template: stringValue(data.template),
    layout: stringValue(data.layout),
    frontmatter: data,
  };
}

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function document(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1">\n  <title>${escapeHtml(title)}</title>\n</head>\n<body>\n${body}\n</body>\n</html>\n`;
}

function defaultPage(page: Page): string {
  const metadata = [
    page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '',
    page.tags.length ? `<p>Tags: ${page.tags.map(escapeHtml).join(', ')}</p>` : '',
  ].filter(Boolean).join('\n');
  return document(page.title, `<main>\n<h1>${escapeHtml(page.title)}</h1>\n${metadata}\n${page.html}\n</main>`);
}

function renderIndex(pages: Page[]): string {
  const links = pages.map((page) => `<li><a href="${encodeURI(page.slug)}.html">${escapeHtml(page.title)}</a></li>`).join('\n');
  return document('Index', `<main>\n<h1>Pages</h1>\n<ul>\n${links}\n</ul>\n</main>`);
}

async function filesIn(directory: string): Promise<string[]> {
  try {
    const entries = await readdir(directory, { withFileTypes: true });
    const files = await Promise.all(entries.map(async (entry) => {
      const path = join(directory, entry.name);
      return entry.isDirectory() ? filesIn(path) : entry.isFile() ? [path] : [];
    }));
    return files.flat();
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
}

function templatePath(directory: string, name: string): string {
  const path = resolve(directory, name.endsWith('.hbs') ? name : `${name}.hbs`);
  if (relative(directory, path).startsWith('..')) throw new Error(`Template must be inside ${directory}: ${name}`);
  return path;
}

async function readTemplate(directory: string, name: string): Promise<string | undefined> {
  try {
    return await readFile(templatePath(directory, name), 'utf8');
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return undefined;
    throw error;
  }
}

async function createTemplates(templateDir: string): Promise<HandlebarsEnvironment> {
  const handlebars = Handlebars.create();
  const partialDir = join(templateDir, 'partials');
  const partialFiles = await filesIn(partialDir);
  await Promise.all(partialFiles.filter((file) => file.endsWith('.hbs')).map(async (file) => {
    const name = relative(partialDir, file).replace(/\.hbs$/, '').split(sep).join('/');
    handlebars.registerPartial(name, await readFile(file, 'utf8'));
  }));
  return handlebars;
}

type HandlebarsEnvironment = ReturnType<typeof Handlebars.create>;

async function renderPage(page: Page, templateDir: string, handlebars: HandlebarsEnvironment): Promise<string> {
  const templateName = page.template ?? 'default';
  const pageSource = await readTemplate(templateDir, templateName);
  if (page.template && !pageSource) throw new Error(`Page template not found: ${page.template}`);
  const body = pageSource
    ? handlebars.compile(pageSource)({ ...page.frontmatter, ...page, content: page.html })
    : defaultPage(page);

  const layoutName = page.layout ?? 'default';
  const layoutSource = await readTemplate(join(templateDir, 'layouts'), layoutName);
  if (page.layout && !layoutSource) throw new Error(`Layout template not found: ${page.layout}`);
  return layoutSource
    ? handlebars.compile(layoutSource)({ ...page.frontmatter, ...page, body })
    : document(page.title, body);
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(path);
    return entry.isFile() && entry.name.toLowerCase().endsWith('.md') ? [path] : [];
  }));
  return files.flat();
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = resolve(options.contentDir ?? 'content');
  const outputDir = resolve(options.outputDir ?? 'dist');
  const templateDir = resolve(options.templateDir ?? 'templates');
  const handlebars = await createTemplates(templateDir);
  const files = await markdownFiles(contentDir);
  const pages = await Promise.all(files.map(async (file) => {
    const page = parsePage(await readFile(file, 'utf8'), relative(contentDir, file));
    page.slug = relative(contentDir, file).replace(/\.md$/i, '').split(sep).join('/');
    return page;
  }));

  await rm(outputDir, { recursive: true, force: true });
  await mkdir(outputDir, { recursive: true });
  await Promise.all(pages.map(async (page) => {
    const target = join(outputDir, `${page.slug}.html`);
    await mkdir(resolve(target, '..'), { recursive: true });
    await writeFile(target, await renderPage(page, templateDir, handlebars), 'utf8');
  }));
  await writeFile(join(outputDir, 'index.html'), renderIndex(pages), 'utf8');
  return pages;
}
