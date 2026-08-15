import fs from 'fs';
import path from 'path';
import Handlebars from 'handlebars';
import { Page } from './types';

export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function formatDate(date: Date): string {
  if (date.getTime() === 0) return '';
  return date.toISOString().slice(0, 10);
}

export const DEFAULT_TEMPLATE_NAME = 'page';
export const DEFAULT_LAYOUT_NAME = 'default';

const DEFAULT_HEADER = `<header>\n  <nav><a href="index.html">Home</a></nav>\n</header>`;
const DEFAULT_FOOTER = `<footer>\n</footer>`;
const DEFAULT_NAV = `<nav><a href="index.html">Home</a></nav>`;

const DEFAULT_LAYOUT = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{{title}}</title>
</head>
<body>
{{{body}}}
</body>
</html>
`;

const DEFAULT_PAGE_TEMPLATE = `{{> header}}
<main>
  <article>
    <h1>{{title}}</h1>
{{#if dateDisplay}}    <time datetime="{{dateIso}}">{{dateDisplay}}</time>
{{/if}}{{#if tags}}    <ul class="tags">
{{#each tags}}      <li>{{this}}</li>
{{/each}}    </ul>
{{/if}}    <div class="content">
{{{html}}}
    </div>
  </article>
</main>
{{> footer}}
`;

const DEFAULT_INDEX_TEMPLATE = `{{> header}}
<main>
  <h1>Index</h1>
  <ul class="posts">
{{#each pages}}    <li><a href="{{slug}}.html">{{title}}</a>{{#if dateDisplay}} &mdash; <time datetime="{{dateIso}}">{{dateDisplay}}</time>{{/if}}{{#if tags}} [{{join tags ", "}}]{{/if}}</li>
{{else}}    <li>No posts</li>
{{/each}}  </ul>
</main>
{{> footer}}
`;

interface PageContext {
  slug: string;
  title: string;
  dateDisplay: string;
  dateIso: string;
  tags: string[];
  html: string;
  template?: string;
  layout?: string;
}

function pageContext(page: Page): PageContext {
  return {
    slug: page.slug,
    title: page.title,
    dateDisplay: formatDate(page.date),
    dateIso: page.date.toISOString(),
    tags: page.tags,
    html: page.html,
    template: page.template,
    layout: page.layout,
  };
}

export class TemplateEngine {
  private readonly templatesDir: string;
  private readonly hbs: typeof Handlebars;

  constructor(templatesDir: string) {
    this.templatesDir = templatesDir;
    this.hbs = Handlebars.create();
    this.hbs.registerHelper('formatDate', formatDate);
    this.hbs.registerHelper('join', (value: unknown, separator: string) =>
      Array.isArray(value) ? value.map(String).join(separator) : ''
    );
    this.registerPartials();
  }

  private file(rel: string): string | null {
    const full = path.join(this.templatesDir, rel);
    if (!fs.existsSync(full)) return null;
    return fs.readFileSync(full, 'utf-8');
  }

  private registerPartials(): void {
    this.hbs.registerPartial('header', DEFAULT_HEADER);
    this.hbs.registerPartial('footer', DEFAULT_FOOTER);
    this.hbs.registerPartial('nav', DEFAULT_NAV);

    const dir = path.join(this.templatesDir, 'partials');
    if (fs.existsSync(dir)) {
      for (const entry of fs.readdirSync(dir)) {
        if (entry.endsWith('.hbs') || entry.endsWith('.handlebars')) {
          const name = path.basename(entry, path.extname(entry));
          this.hbs.registerPartial(name, fs.readFileSync(path.join(dir, entry), 'utf-8'));
        }
      }
    }
  }

  private loadLayout(name: string): string {
    const source =
      this.file(path.join('layouts', `${name}.hbs`)) ??
      this.file(path.join('layouts', `${name}.handlebars`));
    if (source != null) return source;
    if (name === DEFAULT_LAYOUT_NAME) return DEFAULT_LAYOUT;
    throw new Error(`Layout not found: ${name}`);
  }

  private loadTemplate(name: string): string {
    const source = this.file(`${name}.hbs`) ?? this.file(`${name}.handlebars`);
    if (source != null) return source;
    if (name === DEFAULT_TEMPLATE_NAME) return DEFAULT_PAGE_TEMPLATE;
    throw new Error(`Template not found: ${name}`);
  }

  private loadIndexTemplate(): string {
    return this.file('index.hbs') ?? this.file('index.handlebars') ?? DEFAULT_INDEX_TEMPLATE;
  }

  renderPage(page: Page, pages: Page[]): string {
    const templateName = page.template || DEFAULT_TEMPLATE_NAME;
    const layoutName = page.layout || DEFAULT_LAYOUT_NAME;

    const pageTemplate = this.hbs.compile(this.loadTemplate(templateName));
    const layoutTemplate = this.hbs.compile(this.loadLayout(layoutName));

    const context = { ...pageContext(page), pages: pages.map(pageContext) };
    const body = pageTemplate(context);
    return layoutTemplate({ ...context, body });
  }

  renderIndex(pages: Page[]): string {
    const indexTemplate = this.hbs.compile(this.loadIndexTemplate());
    const layoutTemplate = this.hbs.compile(this.loadLayout(DEFAULT_LAYOUT_NAME));

    const context = { title: 'Index', pages: pages.map(pageContext) };
    const body = indexTemplate(context);
    return layoutTemplate({ ...context, body });
  }
}

function firstExisting(files: string[]): string | null {
  for (const file of files) {
    if (fs.existsSync(file)) return file;
  }
  return null;
}

export function pageTemplateSources(templatesDir: string, page: Page): string {
  const templateName = page.template || DEFAULT_TEMPLATE_NAME;
  const layoutName = page.layout || DEFAULT_LAYOUT_NAME;

  const templateFile = firstExisting([
    path.join(templatesDir, `${templateName}.hbs`),
    path.join(templatesDir, `${templateName}.handlebars`),
  ]);
  const templateSource = templateFile
    ? fs.readFileSync(templateFile, 'utf-8')
    : templateName === DEFAULT_TEMPLATE_NAME
    ? DEFAULT_PAGE_TEMPLATE
    : '';

  const layoutFile = firstExisting([
    path.join(templatesDir, 'layouts', `${layoutName}.hbs`),
    path.join(templatesDir, 'layouts', `${layoutName}.handlebars`),
  ]);
  const layoutSource = layoutFile
    ? fs.readFileSync(layoutFile, 'utf-8')
    : layoutName === DEFAULT_LAYOUT_NAME
    ? DEFAULT_LAYOUT
    : '';

  const parts: string[] = [templateName, templateSource, layoutName, layoutSource];

  const builtinPartials: Array<[string, string]> = [
    ['header', DEFAULT_HEADER],
    ['footer', DEFAULT_FOOTER],
    ['nav', DEFAULT_NAV],
  ];
  const partialsDir = path.join(templatesDir, 'partials');
  for (const [name, fallback] of builtinPartials) {
    const file = firstExisting([
      path.join(partialsDir, `${name}.hbs`),
      path.join(partialsDir, `${name}.handlebars`),
    ]);
    parts.push(name, file ? fs.readFileSync(file, 'utf-8') : fallback);
  }

  if (fs.existsSync(partialsDir)) {
    for (const entry of fs.readdirSync(partialsDir).sort()) {
      if (entry.endsWith('.hbs') || entry.endsWith('.handlebars')) {
        parts.push(entry, fs.readFileSync(path.join(partialsDir, entry), 'utf-8'));
      }
    }
  }

  return parts.join('\n');
}

export function renderPage(page: Page, pages: Page[]): string {
  return new TemplateEngine('./templates').renderPage(page, pages);
}

export function renderIndex(pages: Page[]): string {
  return new TemplateEngine('./templates').renderIndex(pages);
}
