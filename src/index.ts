import fs from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface Frontmatter {
  title?: string;
  date?: string | Date;
  tags?: string[] | string;
  [key: string]: unknown;
}

export interface SitePage {
  title: string;
  date?: string;
  tags: string[];
  source: string;
  output: string;
  template?: string;
  layout?: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
}

function markdownFiles(directory: string): string[] {
  if (!fs.existsSync(directory)) return [];

  const files: string[] = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...markdownFiles(entryPath));
    else if (/\.md$/i.test(entry.name)) files.push(entryPath);
  }
  return files.sort((a, b) => a.localeCompare(b));
}

function stringValue(value: unknown): string | undefined {
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  return undefined;
}

function tagsValue(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

function pageFromMarkdown(file: string, contentDir: string): SitePage {
  const parsed = matter(fs.readFileSync(file, 'utf8'));
  const data = parsed.data as Frontmatter;
  const relative = path.relative(contentDir, file);
  const output = relative.replace(/\.md$/i, '.html').split(path.sep).join('/');
  const fallbackTitle = path.basename(relative, path.extname(relative));

  return {
    title: stringValue(data.title) ?? fallbackTitle,
    date: stringValue(data.date),
    tags: tagsValue(data.tags),
    source: relative.split(path.sep).join('/'),
    output,
    ...(stringValue(data.template) ? { template: stringValue(data.template) } : {}),
    ...(stringValue(data.layout) ? { layout: stringValue(data.layout) } : {}),
  };
}

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function indexHtml(pages: SitePage[]): string {
  const items = pages.map((page) => {
    const metadata = page.date ? ` <time>${escapeHtml(page.date)}</time>` : '';
    return `    <li><a href="${escapeHtml(page.output)}">${escapeHtml(page.title)}</a>${metadata}</li>`;
  }).join('\n');
  return `<!doctype html>\n<html>\n<head><meta charset="utf-8"><title>Index</title></head>\n<body>\n  <h1>Pages</h1>\n  <ul>\n${items}\n  </ul>\n</body>\n</html>\n`;
}

type TemplateContext = Record<string, unknown>;

function templateValue(value: unknown): string {
  if (value === null || value === undefined || value === false) return '';
  if (Array.isArray(value)) return value.join(', ');
  return String(value);
}

function lookup(context: TemplateContext, key: string): unknown {
  if (key === 'this' || key === '.') return context;
  return key.split('.').reduce<unknown>((value, part) => {
    if (value && typeof value === 'object') return (value as Record<string, unknown>)[part];
    return undefined;
  }, context);
}

function templateName(name: string): string {
  return name.endsWith('.hbs') ? name : `${name}.hbs`;
}

function readTemplate(directory: string, name: string, kind: 'template' | 'layout'): string | undefined {
  const base = kind === 'layout' ? path.join(directory, 'layouts') : directory;
  const candidate = path.resolve(base, templateName(name));
  if (!candidate.startsWith(`${path.resolve(base)}${path.sep}`)) {
    throw new Error(`Invalid ${kind} path: ${name}`);
  }
  return fs.existsSync(candidate) ? fs.readFileSync(candidate, 'utf8') : undefined;
}

function readPartial(directory: string, name: string): string {
  const partial = readTemplate(path.join(directory, 'partials'), name, 'template');
  if (partial === undefined) throw new Error(`Partial not found: ${name}`);
  return partial;
}

/** Render the small, intentionally data-only Handlebars subset used by sites. */
export function renderTemplate(source: string, context: TemplateContext, templatesDir?: string): string {
  const directory = templatesDir ?? path.resolve('./templates');
  let rendered = source.replace(/\{\{!([\s\S]*?)\}\}/g, '');
  rendered = rendered.replace(/\{\{>\s*([^\s}]+)(?:\s+([^}]+))?\s*\}\}/g, (_match, name: string, partialContext?: string) => {
    const values = partialContext ? lookup(context, partialContext.trim()) : context;
    const child = values && typeof values === 'object' ? values as TemplateContext : context;
    return renderTemplate(readPartial(directory, name), child, directory);
  });
  rendered = rendered.replace(/\{\{\{\s*([^}]+?)\s*\}\}\}/g, (_match, key: string) =>
    templateValue(lookup(context, key.trim())));
  return rendered.replace(/\{\{\s*([^}]+?)\s*\}\}/g, (_match, key: string) =>
    escapeHtml(templateValue(lookup(context, key.trim()))));
}

function renderPage(parsedContent: string, page: SitePage, data: Frontmatter, templatesDir: string): string {
  const body = marked.parse(parsedContent) as string;
  const template = page.template
    ? readTemplate(templatesDir, page.template, 'template')
    : readTemplate(templatesDir, 'default', 'template');
  if (page.template && template === undefined) throw new Error(`Template not found: ${page.template}`);

  const context: TemplateContext = { ...data, page, title: page.title, body, content: body };
  let result = template === undefined ? body : renderTemplate(template, context, templatesDir);
  const layoutName = page.layout ?? (readTemplate(templatesDir, 'default', 'layout') !== undefined ? 'default' : undefined);
  if (layoutName) {
    const layout = readTemplate(templatesDir, layoutName, 'layout');
    if (layout === undefined) throw new Error(`Layout not found: ${layoutName}`);
    result = renderTemplate(layout, { ...context, body: result, content: result }, templatesDir);
  }
  return result;
}

export function buildSite(options: BuildOptions = {}): SitePage[] {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const files = markdownFiles(contentDir);
  const pages: SitePage[] = [];

  fs.rmSync(outputDir, { recursive: true, force: true });
  fs.mkdirSync(outputDir, { recursive: true });

  for (const file of files) {
    const parsed = matter(fs.readFileSync(file, 'utf8'));
    const page = pageFromMarkdown(file, contentDir);
    const destination = path.join(outputDir, page.output);
    fs.mkdirSync(path.dirname(destination), { recursive: true });
    fs.writeFileSync(destination, renderPage(parsed.content, page, parsed.data as Frontmatter, templatesDir));
    pages.push(page);
  }

  pages.sort((a, b) => a.title.localeCompare(b.title));
  fs.writeFileSync(path.join(outputDir, 'index.html'), indexHtml(pages));
  return pages;
}

export { indexHtml, markdownFiles };
