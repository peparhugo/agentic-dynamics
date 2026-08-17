import * as fs from 'fs';
import * as path from 'path';
import Handlebars from 'handlebars';
import { Page } from './ssg';

export const DEFAULT_TEMPLATE_NAME = 'page';
export const DEFAULT_LAYOUT_NAME = 'default';
export const INDEX_TEMPLATE_NAME = 'index';

const TEMPLATE_EXTENSIONS = ['.hbs', '.handlebars'];

export function escapeHtml(input: string): string {
  return input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function pageMeta(page: Page): string {
  const parts: string[] = [];
  if (page.date) {
    parts.push(`<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>`);
  }
  if (page.tags.length > 0) {
    parts.push(
      `<span class="tags">${page.tags.map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join('')}</span>`
    );
  }
  return parts.length > 0 ? `<p class="meta">${parts.join(' ')}</p>` : '';
}

const BUILTIN_PAGE_TEMPLATE = `<article>
  <h1>{{title}}</h1>
  {{{meta}}}
  {{{content}}}
</article>
`;

const BUILTIN_LAYOUT = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{title}}</title>
</head>
<body>
  {{> header}}
  {{> nav}}
  <main>
{{{body}}}
  </main>
  {{> footer}}
</body>
</html>
`;

const BUILTIN_INDEX_TEMPLATE = `<h1>All Posts</h1>
<ul>
{{#each pages}}
  <li><a href="{{slug}}.html">{{title}}</a>{{#if date}} <small>{{date}}</small>{{/if}}</li>
{{else}}
  <li>No posts found.</li>
{{/each}}
</ul>
`;

const BUILTIN_PARTIALS: Record<string, string> = {
  header: `<header>
  <a href="index.html">Home</a>
</header>`,
  nav: '',
  footer: '',
};

type TemplateKind = 'page' | 'layout' | 'index';

export interface TemplateEngineOptions {
  templatesDir?: string;
}

/**
 * Renders pages using Handlebars templates. Templates are discovered in:
 *
 *   ./templates/            page templates (e.g. page.hbs)
 *   ./templates/layouts/    layout templates (e.g. default.hbs)
 *   ./templates/partials/   reusable partials (e.g. header.hbs)
 *
 * A page's frontmatter may specify `template` (which page template to use)
 * and `layout` (which layout to wrap the rendered page in). When omitted, the
 * built-in defaults are used. If the templates directory does not exist, the
 * built-in templates produce the same output as the classic renderer.
 */
export class TemplateEngine {
  private templatesDir: string;
  private env: typeof Handlebars;
  private compiled: Map<string, Handlebars.TemplateDelegate> = new Map();

  constructor(options: TemplateEngineOptions = {}) {
    this.templatesDir = options.templatesDir ?? './templates';
    this.env = Handlebars.create();
    this.registerPartials();
  }

  get hasTemplates(): boolean {
    return fs.existsSync(this.templatesDir);
  }

  private registerPartials(): void {
    for (const [name, source] of Object.entries(BUILTIN_PARTIALS)) {
      this.env.registerPartial(name, source);
    }

    const partialsDir = path.join(this.templatesDir, 'partials');
    if (!fs.existsSync(partialsDir)) {
      return;
    }

    for (const file of fs.readdirSync(partialsDir)) {
      const ext = path.extname(file);
      if (!TEMPLATE_EXTENSIONS.includes(ext)) {
        continue;
      }
      const name = path.basename(file, ext);
      this.env.registerPartial(name, fs.readFileSync(path.join(partialsDir, file), 'utf8'));
    }
  }

  private sourceFor(name: string, kind: TemplateKind): string | undefined {
    const relative =
      kind === 'layout' ? path.join('layouts', `${name}${TEMPLATE_EXTENSIONS[0]}`) : `${name}${TEMPLATE_EXTENSIONS[0]}`;
    const filePath = path.join(this.templatesDir, relative);

    if (fs.existsSync(filePath)) {
      return fs.readFileSync(filePath, 'utf8');
    }

    for (const ext of TEMPLATE_EXTENSIONS.slice(1)) {
      const altPath =
        kind === 'layout' ? path.join(this.templatesDir, 'layouts', `${name}${ext}`) : path.join(this.templatesDir, `${name}${ext}`);
      if (fs.existsSync(altPath)) {
        return fs.readFileSync(altPath, 'utf8');
      }
    }

    return undefined;
  }

  private getTemplate(name: string, kind: TemplateKind, required: boolean): Handlebars.TemplateDelegate {
    const key = `${kind}:${name}`;
    const cached = this.compiled.get(key);
    if (cached) {
      return cached;
    }

    let source = this.sourceFor(name, kind);
    if (source === undefined) {
      if (required) {
        throw new Error(`Template not found: ${path.join(this.templatesDir, name)}`);
      }
      source =
        kind === 'page' ? BUILTIN_PAGE_TEMPLATE : kind === 'layout' ? BUILTIN_LAYOUT : BUILTIN_INDEX_TEMPLATE;
    }

    const template = this.env.compile<Record<string, unknown>>(source);
    this.compiled.set(key, template);
    return template;
  }

  private pageData(page: Page): Record<string, unknown> {
    const data: Record<string, unknown> = { ...page.frontmatter };
    data.title = page.title;
    data.slug = page.slug;
    data.tags = page.tags;
    data.content = page.html;
    data.meta = pageMeta(page);
    if (page.date !== undefined) {
      data.date = page.date;
    }
    return data;
  }

  private layoutData(page: Page, body: string): Record<string, unknown> {
    return { ...this.pageData(page), body };
  }

  private indexData(pages: Page[]): Record<string, unknown> {
    return {
      title: 'Home',
      pages: pages.map((page) => ({
        title: page.title,
        slug: page.slug,
        date: page.date ?? null,
        tags: page.tags,
      })),
    };
  }

  renderPage(page: Page): string {
    const template = this.getTemplate(page.template ?? DEFAULT_TEMPLATE_NAME, 'page', page.template != null);
    const body = template(this.pageData(page));

    const layout = this.getTemplate(page.layout ?? DEFAULT_LAYOUT_NAME, 'layout', page.layout != null);
    return layout(this.layoutData(page, body));
  }

  renderIndex(pages: Page[]): string {
    const template = this.getTemplate(INDEX_TEMPLATE_NAME, 'index', false);
    const body = template(this.indexData(pages));

    const layout = this.getTemplate(DEFAULT_LAYOUT_NAME, 'layout', false);
    return layout({ title: 'Home', body });
  }
}

export function renderPage(page: Page, templatesDir?: string): string {
  return new TemplateEngine({ templatesDir }).renderPage(page);
}

export function renderIndex(pages: Page[], templatesDir?: string): string {
  return new TemplateEngine({ templatesDir }).renderIndex(pages);
}
