import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface Page {
  sourcePath: string;
  outputPath: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  template?: string;
  layout?: string;
  frontmatter: Record<string, unknown>;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
}

function asString(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

function asDateString(value: unknown): string | undefined {
  if (typeof value === 'string') return value;
  if (value instanceof Date && !Number.isNaN(value.valueOf())) return value.toISOString().slice(0, 10);
  return undefined;
}

function asTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((tag): tag is string => typeof tag === 'string');
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function document(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1">\n  <title>${escapeHtml(title)}</title>\n</head>\n<body>\n${body}\n</body>\n</html>\n`;
}

type TemplateContext = Record<string, unknown>;
type TemplateFile = { source: string; filename: string };

function lookup(context: TemplateContext, expression: string): unknown {
  const key = expression.trim().replace(/^this\.?/, '');
  if (!key || key === '.') return context;
  return key.split('.').reduce<unknown>((value, part) => {
    if (part === 'this') return value;
    if (value && typeof value === 'object') return (value as Record<string, unknown>)[part];
    return undefined;
  }, context);
}

function handlebars(template: string, context: TemplateContext, partials: Map<string, TemplateFile>): string {
  const render = (source: string, values: TemplateContext): string => {
    source = source.replace(/{{#(if|unless|each)\s+([^}]+)}}([\s\S]*?){{\/\1}}/g, (_match, kind: string, expression: string, inner: string) => {
      const value = lookup(values, expression);
      if (kind === 'each') {
        if (!Array.isArray(value)) return '';
        return value.map((item, index) => render(inner, { ...values, this: item, '@index': index })).join('');
      }
      const truthy = Array.isArray(value) ? value.length > 0 : Boolean(value);
      return (kind === 'if' ? truthy : !truthy) ? render(inner, values) : '';
    });
    source = source.replace(/{{>\s*([^}\s]+)\s*}}/g, (_match, name: string) => {
      const partial = partials.get(name.replace(/\.(hbs|ejs)$/i, ''));
      return partial ? renderTemplate(partial.source, partial.filename, values, partials) : '';
    });
    source = source.replace(/{{{\s*([^}]+)\s*}}}/g, (_match, expression: string) => String(lookup(values, expression) ?? ''));
    return source.replace(/{{\s*([^}]+)\s*}}/g, (_match, expression: string) => escapeHtml(String(lookup(values, expression) ?? '')));
  };
  return render(template, context);
}

function ejs(template: string, context: TemplateContext, partials: Map<string, TemplateFile>): string {
  const include = (name: string): string => {
    const partial = partials.get(name.replace(/^.*[\\/]partials[\\/]?/, '').replace(/\.(hbs|ejs)$/i, ''));
    return partial ? renderTemplate(partial.source, partial.filename, context, partials) : '';
  };
  return template.replace(/<%([=-])?([\s\S]*?)%>/g, (_match, mode: string | undefined, expression: string) => {
    const value = expression.trim();
    if (value.startsWith('include(')) {
      const name = value.match(/include\(['"]([^'"]+)['"]\)/)?.[1];
      return name ? include(name) : '';
    }
    if (mode === '=') {
      try {
        return escapeHtml(String(Function('context', `with (context) { return (${value}); }`)(context) ?? ''));
      } catch {
        return '';
      }
    }
    if (mode === '-') {
      try {
        return String(Function('context', `with (context) { return (${value}); }`)(context) ?? '');
      } catch {
        return '';
      }
    }
    return '';
  });
}

async function readTemplateFiles(directory: string): Promise<{ templates: Map<string, TemplateFile>; layouts: Map<string, TemplateFile>; partials: Map<string, TemplateFile> }> {
  const templates = new Map<string, TemplateFile>();
  const layouts = new Map<string, TemplateFile>();
  const partials = new Map<string, TemplateFile>();
  const load = async (folder: string, target: Map<string, TemplateFile>): Promise<void> => {
    let entries;
    try { entries = await fs.readdir(folder, { withFileTypes: true }); } catch { return; }
    for (const entry of entries) {
      if (!entry.isFile() || !/\.(hbs|ejs)$/i.test(entry.name)) continue;
      const name = entry.name.replace(/\.(hbs|ejs)$/i, '');
      target.set(name, { source: await fs.readFile(path.join(folder, entry.name), 'utf8'), filename: entry.name });
    }
  };
  await load(directory, templates);
  await load(path.join(directory, 'layouts'), layouts);
  await load(path.join(directory, 'partials'), partials);
  return { templates, layouts, partials };
}

function renderTemplate(source: string, filename: string, context: TemplateContext, partials: Map<string, TemplateFile>): string {
  return filename.endsWith('.ejs') ? ejs(source, context, partials) : handlebars(source, context, partials);
}

async function markdownFiles(directory: string, relative = ''): Promise<string[]> {
  const entries = await fs.readdir(path.join(directory, relative), { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const entryRelative = path.join(relative, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(directory, entryRelative));
    else if (entry.isFile() && /\.md$/i.test(entry.name)) files.push(entryRelative);
  }
  return files;
}

export async function readPages(contentDir: string): Promise<Page[]> {
  const files = (await markdownFiles(contentDir)).sort();
  return Promise.all(files.map(async (relativePath) => {
    const source = await fs.readFile(path.join(contentDir, relativePath), 'utf8');
    const parsed = matter(source);
    const fallbackTitle = path.basename(relativePath, path.extname(relativePath));
    const title = asString(parsed.data.title) ?? fallbackTitle;
    const outputPath = `${relativePath.slice(0, -path.extname(relativePath).length)}.html`;
    return {
      sourcePath: relativePath,
      outputPath,
      title,
      date: asDateString(parsed.data.date),
      tags: asTags(parsed.data.tags),
      html: await marked.parse(parsed.content),
      template: asString(parsed.data.template),
      layout: asString(parsed.data.layout),
      frontmatter: parsed.data
    };
  }));
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const templateFiles = await readTemplateFiles(templatesDir);
  const pages = await readPages(contentDir);
  await fs.rm(outputDir, { recursive: true, force: true });
  await fs.mkdir(outputDir, { recursive: true });

  for (const page of pages) {
    const target = path.join(outputDir, page.outputPath);
    await fs.mkdir(path.dirname(target), { recursive: true });
    const metadata = [page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '', page.tags.length ? `<p>Tags: ${page.tags.map(escapeHtml).join(', ')}</p>` : ''].filter(Boolean).join('\n');
    const article = `<article>\n<h1>${escapeHtml(page.title)}</h1>\n${metadata}\n${page.html}\n</article>`;
    let output = article;
    const templateName = page.template?.replace(/\.(hbs|ejs)$/i, '') ?? 'default';
    const templateFile = templateFiles.templates.get(templateName);
    const context: TemplateContext = { ...page.frontmatter, ...page, content: page.html, body: article, metadata };
    if (templateFile) {
      output = renderTemplate(templateFile.source, templateFile.filename, context, templateFiles.partials);
    }
    const layoutName = page.layout?.replace(/\.(hbs|ejs)$/i, '') ?? (templateFiles.layouts.has('default') ? 'default' : undefined);
    const layoutFile = layoutName ? templateFiles.layouts.get(layoutName) : undefined;
    if (layoutFile) output = renderTemplate(layoutFile.source, layoutFile.filename, { ...context, body: output }, templateFiles.partials);
    if (!templateFile && !layoutFile) output = document(page.title, output);
    await fs.writeFile(target, output);
  }

  const links = pages.map((page) => `<li><a href="${page.outputPath.replaceAll(path.sep, '/')}">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n');
  await fs.writeFile(path.join(outputDir, 'index.html'), document('Home', `<h1>Pages</h1>\n<ul>\n${links}\n</ul>`));
  return pages;
}
