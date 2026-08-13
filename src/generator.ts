import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { basename, extname, join, relative, resolve, sep } from 'node:path';
import matter from 'gray-matter';
import Handlebars from 'handlebars';
import MarkdownIt from 'markdown-it';

export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  template?: string;
  layout?: string | false;
  data: Record<string, unknown>;
}

export interface BuildOptions {
  content?: string;
  output?: string;
  templates?: string;
}

const markdown = new MarkdownIt();

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function toStringValue(value: unknown): string | undefined {
  if (typeof value === 'string') return value;
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  return undefined;
}

function getTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((tag): tag is string => typeof tag === 'string');
  if (typeof value === 'string') return [value];
  return [];
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const filePath = join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(filePath);
    return extname(entry.name).toLowerCase() === '.md' ? [filePath] : [];
  }));
  return files.flat();
}

async function templateFiles(directory: string): Promise<string[]> {
  try {
    const entries = await readdir(directory, { withFileTypes: true });
    const files = await Promise.all(entries.map(async (entry) => {
      const filePath = join(directory, entry.name);
      if (entry.isDirectory()) return templateFiles(filePath);
      return extname(entry.name).toLowerCase() === '.hbs' ? [filePath] : [];
    }));
    return files.flat();
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
}

function templateName(name: string): string {
  return name.endsWith('.hbs') ? name : `${name}.hbs`;
}

const defaultPageTemplate = `<article>
<h1>{{title}}</h1>
{{#if date}}<time datetime="{{date}}">{{date}}</time>{{/if}}
{{#if tags.length}}<p class="tags">{{#each tags}}<span>{{this}}</span> {{/each}}</p>{{/if}}
{{{html}}}
</article>`;

const defaultLayoutTemplate = `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{{title}}</title></head>
<body>
<main>
<nav><a href="/index.html">Home</a></nav>
{{{body}}}
</main>
</body>
</html>
`;

async function createRenderer(templatesDirectory: string) {
  const handlebars = Handlebars.create();
  const files = await templateFiles(templatesDirectory);
  const templates = new Map<string, string>();
  await Promise.all(files.map(async (filePath) => {
    const name = relative(templatesDirectory, filePath).split(sep).join('/');
    templates.set(name, await readFile(filePath, 'utf8'));
  }));

  for (const [name, source] of templates) {
    if (name.startsWith('partials/')) {
      const partialName = name.slice('partials/'.length, -'.hbs'.length);
      handlebars.registerPartial(partialName, source);
    }
  }

  const render = (name: string | undefined, fallback: string, context: Record<string, unknown>, directory = ''): string => {
    const requested = directory + templateName(name ?? 'default');
    const defaultTemplate = directory + 'default.hbs';
    const source = templates.get(requested) ?? (name ? undefined : templates.get(defaultTemplate)) ?? fallback;
    if (!source) throw new Error(`Template not found: ${requested}`);
    return handlebars.compile(source)(context);
  };

  return {
    renderPage(page: Page): string {
      const context = { ...page.data, ...page };
      const body = render(page.template, defaultPageTemplate, context);
      return page.layout === false
        ? body
        : render(page.layout, defaultLayoutTemplate, { ...context, body: new handlebars.SafeString(body) }, 'layouts/');
    },
  };
}

export async function readPages(contentDirectory: string): Promise<Page[]> {
  const files = await markdownFiles(contentDirectory);
  const pages = await Promise.all(files.map(async (filePath) => {
    const parsed = matter(await readFile(filePath, 'utf8'));
    const fileSlug = relative(contentDirectory, filePath).split(sep).join('/').replace(/\.md$/i, '');
    const title = toStringValue(parsed.data.title) ?? basename(fileSlug);
    return {
      slug: fileSlug,
      title,
      date: toStringValue(parsed.data.date),
      tags: getTags(parsed.data.tags),
      html: markdown.render(parsed.content),
      template: toStringValue(parsed.data.template),
      layout: parsed.data.layout === false ? false : toStringValue(parsed.data.layout),
      data: parsed.data,
    };
  }));
  return pages.sort((a, b) => a.title.localeCompare(b.title));
}

function renderIndex(pages: Page[]): string {
  const links = pages.map((page) => `<li><a href="/${escapeHtml(page.slug)}.html">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n');
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Pages</title></head>
<body><main><h1>Pages</h1><ul>${links}</ul></main></body>
</html>
`;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDirectory = resolve(options.content ?? 'content');
  const outputDirectory = resolve(options.output ?? 'dist');
  const templatesDirectory = resolve(options.templates ?? 'templates');
  const pages = await readPages(contentDirectory);
  const renderer = await createRenderer(templatesDirectory);
  await rm(outputDirectory, { recursive: true, force: true });
  await mkdir(outputDirectory, { recursive: true });
  await Promise.all(pages.map(async (page) => {
    const target = join(outputDirectory, `${page.slug}.html`);
    await mkdir(join(target, '..'), { recursive: true });
    await writeFile(target, renderer.renderPage(page), 'utf8');
  }));
  await writeFile(join(outputDirectory, 'index.html'), renderIndex(pages), 'utf8');
  return pages;
}
