import { existsSync } from 'node:fs';
import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { basename, dirname, extname, join, relative } from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  slug: string;
  html: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templateDir?: string;
}

const escapeHtml = (value: string): string => value
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;');

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(path);
    return ['.md', '.markdown'].includes(extname(entry.name).toLowerCase()) ? [path] : [];
  }));
  return files.flat();
}

type TemplateContext = Record<string, unknown>;

async function templateFiles(directory: string): Promise<string[]> {
  if (!existsSync(directory)) return [];
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return templateFiles(path);
    return extname(entry.name).toLowerCase() === '.hbs' ? [path] : [];
  }));
  return files.flat();
}

function valueAt(context: TemplateContext, path: string): unknown {
  return path.split('.').reduce<unknown>((value, key) => (
    value !== null && typeof value === 'object' ? (value as Record<string, unknown>)[key] : undefined
  ), context);
}

function renderTemplate(source: string, context: TemplateContext, partials: Map<string, string>): string {
  const withPartials = source.replace(/{{>\s*([\w./-]+)\s*}}/g, (_match, name: string) => {
    const partial = partials.get(name);
    if (partial === undefined) throw new Error(`Partial does not exist: ${name}`);
    return renderTemplate(partial, context, partials);
  });
  return withPartials
    .replace(/{{{\s*([\w.]+)\s*}}}/g, (_match, path: string) => String(valueAt(context, path) ?? ''))
    .replace(/{{\s*([\w.]+)\s*}}/g, (_match, path: string) => escapeHtml(String(valueAt(context, path) ?? '')));
}

async function loadPartials(partialsDir: string): Promise<Map<string, string>> {
  const files = await templateFiles(partialsDir);
  const partials = await Promise.all(files.map(async (file) => [
    relative(partialsDir, file).replace(/\\/g, '/').replace(/\.hbs$/i, ''),
    await readFile(file, 'utf8'),
  ] as const));
  return new Map(partials);
}

async function readTemplate(directory: string, name: string): Promise<string | undefined> {
  const file = join(directory, `${name.replace(/\.hbs$/i, '')}.hbs`);
  return existsSync(file) ? readFile(file, 'utf8') : undefined;
}

function layout(title: string, content: string): string {
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escapeHtml(title)}</title></head>
<body><main>${content}</main></body>
</html>
`;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = options.contentDir ?? './content';
  const outputDir = options.outputDir ?? './dist';
  const templateDir = options.templateDir ?? './templates';
  if (!existsSync(contentDir)) throw new Error(`Content directory does not exist: ${contentDir}`);

  const partials = await loadPartials(join(templateDir, 'partials'));
  const files = await markdownFiles(contentDir);
  const renderedPages = await Promise.all(files.map(async (file) => {
    const source = await readFile(file, 'utf8');
    const parsed = matter(source);
    const relativePath = relative(contentDir, file).replace(/\\/g, '/');
    const slug = relativePath.replace(/\.(md|markdown)$/i, '.html');
    const fallbackTitle = basename(file, extname(file));
    const title = typeof parsed.data.title === 'string' ? parsed.data.title : fallbackTitle;
    const dateValue = parsed.data.date;
    const date = dateValue === undefined
      ? undefined
      : dateValue instanceof Date
        ? dateValue.toISOString().slice(0, 10)
        : String(dateValue);
    const tags = Array.isArray(parsed.data.tags) ? parsed.data.tags.map(String) : [];
    const html = await marked.parse(parsed.content);
    const page: Page = { title, date, tags, slug, html };
    const context: TemplateContext = { ...parsed.data, ...page, content: html };
    const templateName = typeof parsed.data.template === 'string' ? parsed.data.template : 'default';
    const pageTemplate = await readTemplate(templateDir, templateName);
    const content = pageTemplate === undefined ? html : renderTemplate(pageTemplate, context, partials);
    const layoutName = typeof parsed.data.layout === 'string' ? parsed.data.layout : 'default';
    const layoutTemplate = await readTemplate(join(templateDir, 'layouts'), layoutName);
    return { page, content, layoutTemplate, context };
  }));

  const pages = renderedPages.map(({ page }) => page);

  pages.sort((left, right) => left.title.localeCompare(right.title));
  await rm(outputDir, { recursive: true, force: true });
  await mkdir(outputDir, { recursive: true });

  await Promise.all(renderedPages.map(async ({ page, content, layoutTemplate, context }) => {
    const destination = join(outputDir, page.slug);
    await mkdir(dirname(destination), { recursive: true });
    const output = layoutTemplate === undefined
      ? layout(page.title, content)
      : renderTemplate(layoutTemplate, { ...context, body: content }, partials);
    await writeFile(destination, output, 'utf8');
  }));

  const links = pages.map((page) => `<li><a href="${encodeURI(page.slug)}">${escapeHtml(page.title)}</a></li>`).join('\n');
  await writeFile(join(outputDir, 'index.html'), layout('Index', `<h1>Pages</h1><ul>${links}</ul>`), 'utf8');
  return pages;
}
