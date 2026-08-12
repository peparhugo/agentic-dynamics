import fs from 'fs';
import path from 'path';
import Handlebars from 'handlebars';
import { Page } from './types';

const DEFAULT_LAYOUT = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{title}}</title>
</head>
<body>
  {{{body}}}
</body>
</html>`;

const DEFAULT_PAGE_TEMPLATE = `<h1>{{title}}</h1>
{{#if date}}
<p>Date: {{date}}</p>
{{/if}}
{{#if tags.length}}
<p>Tags: {{#each tags}}{{this}}{{#unless @last}}, {{/unless}}{{/each}}</p>
{{/if}}
{{{content}}}
<p><a href="index.html">Back to index</a></p>`;

const DEFAULT_INDEX_TEMPLATE = `<h1>Site Index</h1>
<ul>
{{#each pages}}
<li><a href="{{slug}}.html">{{title}}</a></li>
{{/each}}
</ul>`;

const DEFAULT_LAYOUT_NAME = 'default';
const DEFAULT_PAGE_NAME = 'page';
const DEFAULT_INDEX_NAME = 'index';

interface TemplateCache {
  [name: string]: Handlebars.TemplateDelegate;
}

export class TemplateEngine {
  private templatesDir: string;
  private compiled: TemplateCache = {};
  private builtins: TemplateCache = {};

  constructor(templatesDir: string) {
    this.templatesDir = path.resolve(templatesDir);
    this.builtins[`layout:${DEFAULT_LAYOUT_NAME}`] = Handlebars.compile(DEFAULT_LAYOUT);
    this.builtins[`page:${DEFAULT_PAGE_NAME}`] = Handlebars.compile(DEFAULT_PAGE_TEMPLATE);
    this.builtins[`page:${DEFAULT_INDEX_NAME}`] = Handlebars.compile(DEFAULT_INDEX_TEMPLATE);
    this.loadPartials();
  }

  private loadPartials(): void {
    const partialsDir = path.join(this.templatesDir, 'partials');
    if (!fs.existsSync(partialsDir)) return;

    const entries = fs.readdirSync(partialsDir, { withFileTypes: true });
    for (const entry of entries) {
      if (!entry.isFile() || !entry.name.endsWith('.hbs')) continue;

      const partialPath = path.join(partialsDir, entry.name);
      const partialName = entry.name.replace(/\.hbs$/, '');
      const source = fs.readFileSync(partialPath, 'utf-8');
      Handlebars.registerPartial(partialName, source);
    }
  }

  private loadFromDisk(kind: 'layout' | 'page', name: string): Handlebars.TemplateDelegate | null {
    const subdir = kind === 'layout' ? 'layouts' : '';
    const dir = subdir ? path.join(this.templatesDir, subdir) : this.templatesDir;
    const filePath = path.join(dir, `${name}.hbs`);

    if (!fs.existsSync(filePath)) {
      return null;
    }

    const cacheKey = `disk:${kind}:${name}`;
    if (this.compiled[cacheKey]) {
      return this.compiled[cacheKey];
    }

    const source = fs.readFileSync(filePath, 'utf-8');
    const compiled = Handlebars.compile(source);
    this.compiled[cacheKey] = compiled;
    return compiled;
  }

  private getTemplate(kind: 'layout' | 'page', name: string): Handlebars.TemplateDelegate {
    const diskTemplate = this.loadFromDisk(kind, name);
    if (diskTemplate) return diskTemplate;

    const builtinKey = `${kind}:${name}`;
    const builtin = this.builtins[builtinKey];
    if (builtin) return builtin;

    const defaultKey = kind === 'layout'
      ? `layout:${DEFAULT_LAYOUT_NAME}`
      : `page:${DEFAULT_PAGE_NAME}`;
    return this.builtins[defaultKey];
  }

  renderPage(page: Page): string {
    const name = page.frontmatter.template || DEFAULT_PAGE_NAME;
    const template = this.getTemplate('page', name);
    return template({
      title: page.frontmatter.title,
      date: page.frontmatter.date,
      tags: page.frontmatter.tags,
      content: page.html,
      slug: page.slug,
    });
  }

  renderIndex(pages: Page[]): string {
    const template = this.getTemplate('page', DEFAULT_INDEX_NAME);
    const flatPages = pages.map((p) => ({
      slug: p.slug,
      title: p.frontmatter.title,
      date: p.frontmatter.date,
      tags: p.frontmatter.tags,
      content: p.html,
    }));
    return template({ pages: flatPages });
  }

  renderLayout(title: string, body: string, layoutName?: string): string {
    const name = layoutName || DEFAULT_LAYOUT_NAME;
    const layout = this.getTemplate('layout', name);
    return layout({ title, body });
  }
}
