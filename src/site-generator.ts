import fs from 'fs/promises';
import path from 'path';
import matter from 'gray-matter';
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
  sourcePath: string;
  outputPath: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  template?: string;
  layout?: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  defaultTemplate?: string;
}

export interface BuildResult {
  pages: Page[];
  indexPath: string;
}

function normalizeTags(value: Frontmatter['tags']): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

function formatDate(value: Frontmatter['date']): string | undefined {
  if (!value) return undefined;
  return value instanceof Date ? value.toISOString().slice(0, 10) : String(value);
}

const pageFrontmatter = new WeakMap<Page, Frontmatter>();

export function parseMarkdown(source: string, sourcePath = ''): Page {
  const parsed = matter(source);
  const data = parsed.data as Frontmatter;
  const title = typeof data.title === 'string' && data.title.trim()
    ? data.title.trim()
    : path.basename(sourcePath, path.extname(sourcePath));

  const page: Page = {
    sourcePath,
    outputPath: sourcePath.replace(/\.md$/i, '.html'),
    title,
    date: formatDate(data.date),
    tags: normalizeTags(data.tags),
    html: marked.parse(parsed.content),
    template: typeof data.template === 'string' ? data.template : undefined,
    layout: typeof data.layout === 'string' ? data.layout : undefined,
  };
  pageFrontmatter.set(page, data);
  return page;
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(entryPath));
    else if (entry.isFile() && /\.md$/i.test(entry.name)) files.push(entryPath);
  }
  return files.sort();
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[character] as string));
}

function document(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>${escapeHtml(title)}</title>\n</head>\n<body>\n${body}\n</body>\n</html>\n`;
}

function pageDocument(page: Page): string {
  const metadata = [page.date, ...page.tags].filter(Boolean).map(escapeHtml).join(' | ');
  return document(page.title, `<main>\n<h1>${escapeHtml(page.title)}</h1>\n${metadata ? `<p>${metadata}</p>\n` : ''}${page.html}</main>`);
}

function indexDocument(pages: Page[]): string {
  const links = pages.map((page) => {
    const metadata = [page.date, ...page.tags].filter(Boolean).map(escapeHtml).join(' | ');
    return `<li><a href="${encodeURI(page.outputPath)}">${escapeHtml(page.title)}</a>${metadata ? ` <small>${metadata}</small>` : ''}</li>`;
  }).join('\n');
  return document('Index', `<main>\n<h1>Pages</h1>\n<ul>\n${links}\n</ul>\n</main>`);
}

type TemplateValue = Record<string, unknown>;

function lookup(context: TemplateValue, key: string): unknown {
  if (key === 'this' || key === '.') return context;
  return key.split('.').reduce<unknown>((value, part) => {
    if (part === 'this') return value;
    if (value && typeof value === 'object') return (value as Record<string, unknown>)[part];
    return undefined;
  }, context);
}

function escapeTemplate(value: unknown): string {
  return escapeHtml(value == null ? '' : String(value));
}

function truthy(value: unknown): boolean {
  return Boolean(value) && (!Array.isArray(value) || value.length > 0);
}

// A small Handlebars-compatible renderer keeps the generator usable without a runtime plugin.
function renderTemplate(source: string, context: TemplateValue, partials: Map<string, string>): string {
  const renderBlock = (input: string, scope: TemplateValue): string => {
    let output = input;
    const blockPattern = /{{#(if|each)\s+([^}]+)}}([\s\S]*?){{\/\1}}/g;
    output = output.replace(blockPattern, (_match, type: string, expression: string, content: string) => {
      const value = lookup(scope, expression.trim());
      if (type === 'if') return truthy(value) ? renderBlock(content, scope) : '';
      if (!Array.isArray(value)) return '';
      return value.map((item) => renderBlock(content, typeof item === 'object' && item !== null
        ? { ...scope, ...(item as TemplateValue), this: item }
        : { ...scope, this: item })).join('');
    });
    output = output.replace(/{{>\s*([\w./-]+)\s*}}/g, (_match, name: string) => {
      const partial = partials.get(name);
      return partial === undefined ? '' : renderBlock(partial, scope);
    });
    output = output.replace(/{{{\s*([^}]+?)\s*}}}/g, (_match, expression: string) => {
      const value = lookup(scope, expression.trim());
      return value == null ? '' : String(value);
    });
    return output.replace(/{{\s*([^{}]+?)\s*}}/g, (_match, expression: string) => {
      const value = lookup(scope, expression.trim());
      return escapeTemplate(value);
    });
  };
  return renderBlock(source, context);
}

async function loadTemplates(directory: string): Promise<Map<string, string>> {
  const result = new Map<string, string>();
  let entries;
  try {
    entries = await fs.readdir(directory, { withFileTypes: true });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return result;
    throw error;
  }
  for (const entry of entries) {
    if (!entry.isFile() || !/\.(hbs|ejs)$/i.test(entry.name)) continue;
    const name = entry.name.replace(/\.(hbs|ejs)$/i, '');
    result.set(name, await fs.readFile(path.join(directory, entry.name), 'utf8'));
  }
  return result;
}

async function renderWithTemplates(
  page: Page,
  templatesDir: string,
  defaultTemplate: string,
): Promise<string | undefined> {
  const templates = await loadTemplates(templatesDir);
  const partials = await loadTemplates(path.join(templatesDir, 'partials'));
  const selected = page.template || defaultTemplate;
  const template = templates.get(selected.replace(/\.(hbs|ejs)$/i, ''));
  if (template === undefined) {
    if (page.template) throw new Error(`Template not found: ${page.template}`);
    return undefined;
  }
  const context: TemplateValue = {
    ...pageFrontmatter.get(page),
    page,
    title: page.title,
    date: page.date,
    tags: page.tags,
    body: page.html,
  };
  let rendered = renderTemplate(template, context, partials);
  if (page.layout) {
    const layouts = await loadTemplates(path.join(templatesDir, 'layouts'));
    const layout = layouts.get(page.layout.replace(/\.(hbs|ejs)$/i, ''));
    if (layout === undefined) throw new Error(`Layout not found: ${page.layout}`);
    rendered = renderTemplate(layout, { ...context, body: rendered }, partials);
  }
  return rendered;
}

export async function buildSite(options: BuildOptions = {}): Promise<BuildResult> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const defaultTemplate = options.defaultTemplate ?? 'default';
  const sourceFiles = await markdownFiles(contentDir);
  const pages = await Promise.all(sourceFiles.map(async (sourcePath) => {
    const source = await fs.readFile(sourcePath, 'utf8');
    const relativePath = path.relative(contentDir, sourcePath);
    const page = parseMarkdown(source, relativePath);
    const destination = path.join(outputDir, page.outputPath);
    await fs.mkdir(path.dirname(destination), { recursive: true });
    const templated = await renderWithTemplates(page, templatesDir, defaultTemplate);
    await fs.writeFile(destination, templated ?? pageDocument(page), 'utf8');
    return page;
  }));
  pages.sort((a, b) => a.outputPath.localeCompare(b.outputPath));
  await fs.mkdir(outputDir, { recursive: true });
  const indexPath = path.join(outputDir, 'index.html');
  await fs.writeFile(indexPath, indexDocument(pages), 'utf8');
  return { pages, indexPath };
}
