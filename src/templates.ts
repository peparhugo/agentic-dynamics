import * as fs from 'fs';
import * as path from 'path';
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

export const DEFAULT_TEMPLATE_NAME = 'page';
export const DEFAULT_LAYOUT_NAME = 'default';

const DEFAULT_LAYOUT_SOURCE = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{title}}</title>
</head>
<body>
{{{body}}}
</body>
</html>
`;

const DEFAULT_PAGE_TEMPLATE_SOURCE = `<article>
<h1>{{title}}</h1>
{{#if date}}<p class="date">{{date}}</p>{{/if}}
{{#if tags.length}}<ul class="tags">
{{#each tags}}<li>{{this}}</li>
{{/each}}</ul>{{/if}}
<div class="content">
{{{content}}}
</div>
<p><a href="index.html">&larr; Back to index</a></p>
</article>`;

const DEFAULT_INDEX_TEMPLATE_SOURCE = `<h1>Site Index</h1>
<ul class="pages">
{{#each pages}}<li><a href="{{outputPath}}">{{title}}</a>{{#if date}} <span class="date">{{date}}</span>{{/if}}</li>
{{/each}}</ul>`;

/**
 * Compiles and caches Handlebars templates, layouts, and partials sourced
 * from a templates directory on disk, falling back to sane built-in
 * defaults when the default-named template/layout files are absent so a
 * project works out of the box without a templates/ directory.
 */
export class TemplateEngine {
  private handlebars: typeof Handlebars;
  private templatesDir: string;
  private layoutsDir: string;
  private partialsDir: string;
  private compiledCache = new Map<string, HandlebarsTemplateDelegate>();

  constructor(templatesDir: string) {
    this.handlebars = Handlebars.create();
    this.templatesDir = path.resolve(templatesDir);
    this.layoutsDir = path.join(this.templatesDir, 'layouts');
    this.partialsDir = path.join(this.templatesDir, 'partials');
    this.registerPartials();
  }

  private registerPartials(): void {
    if (!fs.existsSync(this.partialsDir)) {
      return;
    }
    const entries = fs.readdirSync(this.partialsDir).filter((f) => f.endsWith('.hbs'));
    for (const entry of entries) {
      const name = entry.replace(/\.hbs$/, '');
      const source = fs.readFileSync(path.join(this.partialsDir, entry), 'utf-8');
      this.handlebars.registerPartial(name, source);
    }
  }

  private compile(dir: string, name: string, fallbackSource: string | undefined, kind: string): HandlebarsTemplateDelegate {
    const cacheKey = `${dir}::${name}`;
    const cached = this.compiledCache.get(cacheKey);
    if (cached) {
      return cached;
    }
    const filePath = path.join(dir, `${name}.hbs`);
    let source: string;
    if (fs.existsSync(filePath)) {
      source = fs.readFileSync(filePath, 'utf-8');
    } else if (fallbackSource !== undefined) {
      source = fallbackSource;
    } else {
      throw new Error(`${kind} not found: ${filePath}`);
    }
    const compiled = this.handlebars.compile(source);
    this.compiledCache.set(cacheKey, compiled);
    return compiled;
  }

  renderTemplate(name: string, context: Record<string, unknown>): string {
    const fallback = name === DEFAULT_TEMPLATE_NAME ? DEFAULT_PAGE_TEMPLATE_SOURCE : undefined;
    return this.compile(this.templatesDir, name, fallback, 'Template')(context);
  }

  renderIndexTemplate(context: Record<string, unknown>): string {
    return this.compile(this.templatesDir, 'index', DEFAULT_INDEX_TEMPLATE_SOURCE, 'Template')(context);
  }

  renderLayout(name: string, context: Record<string, unknown>): string {
    const fallback = name === DEFAULT_LAYOUT_NAME ? DEFAULT_LAYOUT_SOURCE : undefined;
    return this.compile(this.layoutsDir, name, fallback, 'Layout')(context);
  }
}

export function renderPage(page: Page, engine: TemplateEngine): string {
  const templateName = page.template || DEFAULT_TEMPLATE_NAME;
  const body = engine.renderTemplate(templateName, {
    title: page.title,
    date: page.date,
    tags: page.tags,
    content: page.html,
  });
  const layoutName = page.layout || DEFAULT_LAYOUT_NAME;
  return engine.renderLayout(layoutName, { title: page.title, body });
}

export function renderIndex(pages: Page[], engine: TemplateEngine): string {
  const sorted = [...pages].sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  const body = engine.renderIndexTemplate({ pages: sorted });
  return engine.renderLayout(DEFAULT_LAYOUT_NAME, { title: 'Site Index', body });
}
