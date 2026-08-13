import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { basename, extname, join, relative, resolve, sep } from 'node:path';
import matter from 'gray-matter';
import Handlebars from 'handlebars';
import { marked } from 'marked';

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  outputPath: string;
  html: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
}

const escapeHtml = (value: string): string => value
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;');

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const paths = await Promise.all(entries.map(async (entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      return markdownFiles(path);
    }
    return entry.isFile() && ['.md', '.markdown'].includes(extname(entry.name).toLowerCase()) ? [path] : [];
  }));
  return paths.flat();
}

async function templateFiles(directory: string): Promise<string[]> {
  try {
    const entries = await readdir(directory, { withFileTypes: true });
    const paths = await Promise.all(entries.map(async (entry) => {
      const path = join(directory, entry.name);
      if (entry.isDirectory()) return templateFiles(path);
      return entry.isFile() && extname(entry.name).toLowerCase() === '.hbs' ? [path] : [];
    }));
    return paths.flat();
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
}

function asString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

function asTags(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.filter((tag): tag is string => typeof tag === 'string').map((tag) => tag.trim()).filter(Boolean);
  }
  return typeof value === 'string' ? value.split(',').map((tag) => tag.trim()).filter(Boolean) : [];
}

function document(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1">\n  <title>${escapeHtml(title)}</title>\n</head>\n<body>\n  <main>\n${body}\n  </main>\n</body>\n</html>\n`;
}

interface RenderContext {
  title: string;
  date?: string;
  tags: string[];
  content: string;
  body?: string;
  [key: string]: unknown;
}

async function loadTemplates(templatesDir: string): Promise<Map<string, Handlebars.TemplateDelegate>> {
  const templates = new Map<string, Handlebars.TemplateDelegate>();
  const files = await templateFiles(templatesDir);
  await Promise.all(files.map(async (file) => {
    const name = relative(templatesDir, file).replace(/\\/g, '/').replace(/\.hbs$/i, '');
    templates.set(name, Handlebars.compile(await readFile(file, 'utf8')));
  }));
  for (const [name, template] of templates) {
    if (name.startsWith('partials/')) Handlebars.registerPartial(name.slice('partials/'.length), template);
  }
  return templates;
}

function renderTemplate(templates: Map<string, Handlebars.TemplateDelegate>, name: string, context: RenderContext): string | undefined {
  return templates.get(name)?.(context);
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = resolve(options.contentDir ?? 'content');
  const outputDir = resolve(options.outputDir ?? 'dist');
  const templatesDir = resolve(options.templatesDir ?? 'templates');
  const templates = await loadTemplates(templatesDir);
  const files = await markdownFiles(contentDir);
  const pages = await Promise.all(files.map(async (file): Promise<Page & { template?: string; layout?: string; data: Record<string, unknown> }> => {
    const parsed = matter(await readFile(file, 'utf8'));
    const sourcePath = relative(contentDir, file);
    const outputPath = sourcePath.replace(/\.(md|markdown)$/i, '.html').split(sep).join('/');
    const title = asString(parsed.data.title) ?? basename(file, extname(file));
    const date = asString(parsed.data.date);
    const tags = asTags(parsed.data.tags);
    return {
      title,
      date,
      tags,
      outputPath,
      html: await marked.parse(parsed.content),
      template: asString(parsed.data.template),
      layout: asString(parsed.data.layout),
      data: parsed.data,
    };
  }));

  pages.sort((a, b) => a.title.localeCompare(b.title));
  await rm(outputDir, { recursive: true, force: true });
  await mkdir(outputDir, { recursive: true });

  await Promise.all(pages.map(async (page) => {
    const destination = join(outputDir, page.outputPath);
    await mkdir(resolve(destination, '..'), { recursive: true });
    const metadata = [page.date, page.tags.length ? `Tags: ${page.tags.map(escapeHtml).join(', ')}` : ''].filter(Boolean).join(' | ');
    const content = page.html.trim();
    const context: RenderContext = { ...page.data, title: page.title, date: page.date, tags: page.tags, content };
    const pageBody = renderTemplate(templates, page.template ?? 'default', context)
      ?? `    <article>\n      <h1>${escapeHtml(page.title)}</h1>${metadata ? `\n      <p>${metadata}</p>` : ''}\n      ${content}\n    </article>`;
    const layoutName = page.layout ?? (templates.has('layouts/default') ? 'default' : undefined);
    const html = layoutName
      ? renderTemplate(templates, `layouts/${layoutName}`, { ...context, body: pageBody }) ?? pageBody
      : templates.has(page.template ?? 'default') ? pageBody : document(page.title, pageBody);
    await writeFile(destination, html);
  }));

  const links = pages.map((page) => `      <li><a href="${encodeURI(page.outputPath)}">${escapeHtml(page.title)}</a></li>`).join('\n');
  await writeFile(join(outputDir, 'index.html'), document('Index', `    <h1>Pages</h1>\n    <ul>\n${links}\n    </ul>`));
  return pages;
}
