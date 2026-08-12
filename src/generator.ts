import fs from 'node:fs';
import path from 'node:path';
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
  [key: string]: unknown;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  templateDir?: string;
}

function markdownFiles(directory: string): string[] {
  if (!fs.existsSync(directory)) return [];
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const filename = path.join(directory, entry.name);
    return entry.isDirectory() ? markdownFiles(filename) : /\.md$/i.test(entry.name) ? [filename] : [];
  });
}

function asDate(value: unknown): number {
  const time = value instanceof Date ? value.getTime() : Date.parse(String(value ?? ''));
  return Number.isNaN(time) ? 0 : time;
}

function pageFromFile(filename: string, contentDir: string): Page {
  const parsed = matter(fs.readFileSync(filename, 'utf8'));
  const relative = path.relative(contentDir, filename);
  const slug = relative.replace(/\.md$/i, '').split(path.sep).join('/');
  const title = typeof parsed.data.title === 'string' ? parsed.data.title : path.basename(slug);
  const rawTags = parsed.data.tags;
  const tags = Array.isArray(rawTags) ? rawTags.map(String) : typeof rawTags === 'string' ? rawTags.split(',').map((tag) => tag.trim()).filter(Boolean) : [];
  return {
    ...parsed.data,
    title,
    date: parsed.data.date instanceof Date ? parsed.data.date.toISOString() : parsed.data.date == null ? undefined : String(parsed.data.date),
    tags,
    slug,
    html: marked.parse(parsed.content) as string,
    template: typeof parsed.data.template === 'string' ? parsed.data.template : undefined,
    layout: typeof parsed.data.layout === 'string' ? parsed.data.layout : undefined
  };
}

function document(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>${title}</title>\n</head>\n<body>\n${body}\n</body>\n</html>\n`;
}

function templateFile(directory: string, name: string, subdirectory = ''): string | undefined {
  const requested = path.extname(name) ? name : `${name}.hbs`;
  const filename = path.join(directory, subdirectory, requested);
  return fs.existsSync(filename) ? filename : undefined;
}

function createRenderer(directory: string) {
  const handlebars = Handlebars.create();
  const partialsDir = path.join(directory, 'partials');
  if (fs.existsSync(partialsDir)) {
    for (const filename of fs.readdirSync(partialsDir)) {
      if (!/\.hbs$/i.test(filename)) continue;
      const name = filename.replace(/\.hbs$/i, '');
      handlebars.registerPartial(name, fs.readFileSync(path.join(partialsDir, filename), 'utf8'));
    }
  }

  const render = (name: string, context: Record<string, unknown>): string | undefined => {
    const filename = templateFile(directory, name);
    return filename ? handlebars.compile(fs.readFileSync(filename, 'utf8'))(context) : undefined;
  };
  const renderFile = (filename: string, context: Record<string, unknown>): string =>
    handlebars.compile(fs.readFileSync(filename, 'utf8'))(context);
  return { render, renderFile };
}

function renderWithLayout(context: Record<string, unknown>, templatesDir: string, rendered: string, renderer = createRenderer(templatesDir)): string {
  const layoutName = typeof context.layout === 'string'
    ? context.layout
    : templateFile(templatesDir, 'default', 'layouts') ? 'default' : undefined;
  if (!layoutName) return rendered;
  const layout = templateFile(templatesDir, layoutName, 'layouts');
  if (!layout) throw new Error(`Layout template not found: ${layoutName}`);
  return renderer.renderFile(layout, { ...context, body: rendered });
}

function renderPage(page: Page, templatesDir: string, fallback: string): string {
  const renderer = createRenderer(templatesDir);
  const templateName = page.template ?? (templateFile(templatesDir, 'page') ? 'page' : 'default');
  const context = { ...page, content: page.html, page } as Record<string, unknown>;
  const rendered = renderer.render(templateName, context) ?? fallback;
  return renderWithLayout(context, templatesDir, rendered);
}

function renderIndex(pages: Page[], templatesDir: string, fallback: string): string {
  const renderer = createRenderer(templatesDir);
  const context = { pages, title: 'Index' };
  const rendered = renderer.render('index', context) ?? fallback;
  return renderWithLayout(context, templatesDir, rendered);
}

export function buildSite(options: BuildOptions = {}): Page[] {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const templatesDir = path.resolve(options.templatesDir ?? options.templateDir ?? './templates');
  const pages = markdownFiles(contentDir)
    .map((filename) => pageFromFile(filename, contentDir))
    .sort((a, b) => asDate(b.date) - asDate(a.date));

  fs.rmSync(outputDir, { recursive: true, force: true });
  fs.mkdirSync(outputDir, { recursive: true });
  for (const page of pages) {
    const target = path.join(outputDir, `${page.slug}.html`);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    const tags = page.tags.length > 0 ? `<p class="tags">Tags: ${page.tags.join(', ')}</p>\n` : '';
    const body = `<article>\n<h1>${page.title}</h1>\n${tags}${page.html}\n</article>`;
    fs.writeFileSync(target, renderPage(page, templatesDir, document(page.title, body)));
  }
  const items = pages.map((page) => `<li><a href="${page.slug}.html">${page.title}</a>${page.date ? ` <time>${page.date}</time>` : ''}${page.tags.length ? ` <span class="tags">${page.tags.join(', ')}</span>` : ''}</li>`).join('\n');
  const indexBody = `<main>\n<h1>Pages</h1>\n<ul>\n${items}\n</ul>\n</main>`;
  fs.writeFileSync(path.join(outputDir, 'index.html'), renderIndex(pages, templatesDir, document('Index', indexBody)));
  return pages;
}
