import fs from 'node:fs/promises';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface PageMetadata {
  title: string;
  date?: string;
  tags: string[];
  template?: string;
  layout?: string;
}

export interface Page {
  sourcePath: string;
  outputPath: string;
  metadata: PageMetadata;
  html: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
}

const markdownExtensions = new Set(['.md', '.markdown']);

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function stringValue(value: unknown): string | undefined {
  if (value === undefined || value === null) return undefined;
  return value instanceof Date ? value.toISOString().slice(0, 10) : String(value);
}

function getMetadata(data: Record<string, unknown>, sourcePath: string): PageMetadata {
  const fallbackTitle = path.basename(sourcePath, path.extname(sourcePath));
  const tagsValue = data.tags;
  const tags = Array.isArray(tagsValue)
    ? tagsValue.map(String)
    : typeof tagsValue === 'string'
      ? tagsValue.split(',').map((tag) => tag.trim()).filter(Boolean)
      : [];

  return {
    title: stringValue(data.title) ?? fallbackTitle,
    date: stringValue(data.date),
    tags,
    template: stringValue(data.template),
    layout: stringValue(data.layout),
  };
}

type TemplateContext = Record<string, unknown>;

function contextValue(context: TemplateContext, expression: string): unknown {
  const name = expression.trim();
  if (!name) return '';
  if ((name.startsWith('"') && name.endsWith('"')) || (name.startsWith("'") && name.endsWith("'"))) {
    return name.slice(1, -1);
  }
  return name.split('.').reduce<unknown>((value, key) => {
    if (value && typeof value === 'object') return (value as Record<string, unknown>)[key];
    return undefined;
  }, context);
}

function templateString(value: unknown): string {
  if (value === undefined || value === null) return '';
  if (Array.isArray(value)) return value.join(', ');
  return String(value);
}

function renderHandlebars(source: string, context: TemplateContext, partials: Map<string, string>): string {
  let result = source;
  // Blocks are intentionally small but cover the useful template primitives for a static site.
  result = result.replace(/\{\{#if\s+([^}]+)\}\}([\s\S]*?)\{\{\/if\}\}/g, (_, expression: string, content: string) =>
    contextValue(context, expression) ? renderHandlebars(content, context, partials) : '');
  result = result.replace(/\{\{#each\s+([^}]+)\}\}([\s\S]*?)\{\{\/each\}\}/g, (_, expression: string, content: string) => {
    const values = contextValue(context, expression);
    if (!Array.isArray(values)) return '';
    return values.map((value) => renderHandlebars(content, { ...context, this: value, '.': value }, partials)).join('');
  });
  result = result.replace(/\{\{>\s*([\w./-]+)(?:\s+[^}]*)?\s*\}\}/g, (_, name: string) => {
    const partial = partials.get(name) ?? partials.get(path.basename(name, path.extname(name)));
    return partial ? renderHandlebars(partial, context, partials) : '';
  });
  result = result.replace(/\{\{\{\s*([^}]+)\s*\}\}\}/g, (_, expression: string) => templateString(contextValue(context, expression)));
  return result.replace(/\{\{\s*([^}]+)\s*\}\}/g, (_, expression: string) => escapeHtml(templateString(contextValue(context, expression))));
}

function renderEjs(source: string, context: TemplateContext, partials: Map<string, string>): string {
  let result = source.replace(/<%[-=]\s*include\(\s*['"]([^'"]+)['"]\s*\)\s*%>/g, (_, name: string) => {
    const partial = partials.get(name) ?? partials.get(path.basename(name, path.extname(name)));
    return partial ? renderEjs(partial, context, partials) : '';
  });
  result = result.replace(/<%-\s*([^%]+?)\s*%>/g, (_, expression: string) => templateString(contextValue(context, expression)));
  return result.replace(/<%=\s*([^%]+?)\s*%>/g, (_, expression: string) => escapeHtml(templateString(contextValue(context, expression))));
}

function renderTemplate(source: string, filename: string, context: TemplateContext, partials: Map<string, string>): string {
  return path.extname(filename).toLowerCase() === '.ejs'
    ? renderEjs(source, context, partials)
    : renderHandlebars(source, context, partials);
}

async function loadTemplate(directory: string, requested: string | undefined, fallback: string): Promise<{ name: string; source: string } | undefined> {
  const name = requested ?? fallback;
  const candidates = path.extname(name) ? [name] : [`${name}.hbs`, `${name}.ejs`, `${name}.handlebars`];
  for (const candidate of candidates) {
    try {
      return { name: candidate, source: await fs.readFile(path.join(directory, candidate), 'utf8') };
    } catch (error: unknown) {
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
    }
  }
  if (requested) throw new Error(`Template not found: ${requested}`);
  return undefined;
}

async function loadPartials(directory: string): Promise<Map<string, string>> {
  const partials = new Map<string, string>();
  try {
    const entries = await fs.readdir(directory, { withFileTypes: true });
    for (const entry of entries) {
      if (!entry.isFile() || !['.hbs', '.handlebars', '.ejs'].includes(path.extname(entry.name).toLowerCase())) continue;
      partials.set(entry.name, await fs.readFile(path.join(directory, entry.name), 'utf8'));
      partials.set(path.basename(entry.name, path.extname(entry.name)), partials.get(entry.name)!);
    }
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
  }
  return partials;
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(entryPath));
    else if (markdownExtensions.has(path.extname(entry.name).toLowerCase())) files.push(entryPath);
  }
  return files.sort((a, b) => a.localeCompare(b));
}

function pageDocument(page: Page): string {
  const { metadata } = page;
  const date = metadata.date ? `<time>${escapeHtml(metadata.date)}</time>` : '';
  const tags = metadata.tags.length
    ? `<ul class="tags">${metadata.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>`
    : '';
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(metadata.title)}</title>
</head>
<body>
  <main>
    <article>
      <header><h1>${escapeHtml(metadata.title)}</h1>${date}${tags}</header>
      ${page.html}
    </article>
  </main>
</body>
</html>
`;
}

async function renderPageDocument(page: Page, templatesDir: string): Promise<string> {
  const partials = await loadPartials(path.join(templatesDir, 'partials'));
  const context: TemplateContext = {
    ...page.metadata,
    content: page.html,
    body: page.html,
    page,
    metadata: page.metadata,
  };
  const template = await loadTemplate(templatesDir, page.metadata.template, 'default');
  let document = template
    ? renderTemplate(template.source, template.name, context, partials)
    : pageDocument(page);

  const layout = await loadTemplate(path.join(templatesDir, 'layouts'), page.metadata.layout, 'default');
  if (layout) {
    document = renderTemplate(layout.source, layout.name, { ...context, body: document }, partials);
  }
  return document;
}

function indexDocument(pages: Page[], outputDir: string): string {
  const items = pages.map((page) => {
    const href = path.relative(outputDir, page.outputPath).replaceAll(path.sep, '/');
    const date = page.metadata.date ? ` <time>${escapeHtml(page.metadata.date)}</time>` : '';
    return `      <li><a href="${escapeHtml(href)}">${escapeHtml(page.metadata.title)}</a>${date}</li>`;
  }).join('\n');
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Index</title>
</head>
<body>
  <main><h1>Pages</h1><ul>${items}</ul></main>
</body>
</html>
`;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const files = await markdownFiles(contentDir);
  const pages: Page[] = [];

  for (const sourcePath of files) {
    const relativePath = path.relative(contentDir, sourcePath);
    const outputPath = path.join(outputDir, relativePath.replace(/\.(md|markdown)$/i, '.html'));
    const parsed = matter(await fs.readFile(sourcePath, 'utf8'));
    pages.push({
      sourcePath,
      outputPath,
      metadata: getMetadata(parsed.data as Record<string, unknown>, sourcePath),
      html: await marked.parse(parsed.content),
    });
  }

  await fs.mkdir(outputDir, { recursive: true });
  for (const page of pages) {
    await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
    await fs.writeFile(page.outputPath, await renderPageDocument(page, templatesDir), 'utf8');
  }
  await fs.writeFile(path.join(outputDir, 'index.html'), indexDocument(pages, outputDir), 'utf8');
  return pages;
}
