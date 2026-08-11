import fs from 'fs';
import path from 'path';
import Handlebars from 'handlebars';
import { PageData } from './types';

export interface TemplateConfig {
  templatesDir: string;
}

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

const DEFAULT_PAGE_TEMPLATE = `
  <header>
    <h1>{{title}}</h1>
    {{#if date}}<time>{{date}}</time>{{/if}}
    {{#if tags}}<p>Tags: {{tags}}</p>{{/if}}
  </header>
  <main>
    {{{content}}}
  </main>
  <footer>
    <a href="index.html">&larr; Back to index</a>
  </footer>`;

const DEFAULT_INDEX_TEMPLATE = `
  <header>
    <h1>Blog</h1>
  </header>
  <main>
    {{#if pages.length}}
      {{#each pages}}
    <article>
      <h2><a href="{{slug}}.html">{{title}}</a></h2>
      {{#if date}}<time>{{date}}</time>{{/if}}
      {{#if tags}}<p>Tags: {{tags}}</p>{{/if}}
    </article>
      {{/each}}
    {{else}}
    <p>No posts yet.</p>
    {{/if}}
  </main>`;

export class TemplateEngine {
  private templatesDir: string;
  private pageTemplates: Map<string, HandlebarsTemplateDelegate> = new Map();
  private layouts: Map<string, HandlebarsTemplateDelegate> = new Map();
  private initialized = false;

  constructor(config: TemplateConfig) {
    this.templatesDir = config.templatesDir;
  }

  init(): void {
    if (this.initialized) return;
    this.initialized = true;

    if (!fs.existsSync(this.templatesDir)) return;

    const partialsDir = path.join(this.templatesDir, 'partials');
    if (fs.existsSync(partialsDir)) {
      for (const file of fs.readdirSync(partialsDir)) {
        if (file.endsWith('.hbs')) {
          const name = file.replace(/\.hbs$/, '');
          const content = fs.readFileSync(path.join(partialsDir, file), 'utf-8');
          Handlebars.registerPartial(name, content);
        }
      }
    }

    const layoutsDir = path.join(this.templatesDir, 'layouts');
    if (fs.existsSync(layoutsDir)) {
      for (const file of fs.readdirSync(layoutsDir)) {
        if (file.endsWith('.hbs')) {
          const name = file.replace(/\.hbs$/, '');
          const content = fs.readFileSync(path.join(layoutsDir, file), 'utf-8');
          this.layouts.set(name, Handlebars.compile(content));
        }
      }
    }

    for (const file of fs.readdirSync(this.templatesDir)) {
      const fullPath = path.join(this.templatesDir, file);
      if (file.endsWith('.hbs') && !fs.statSync(fullPath).isDirectory()) {
        const name = file.replace(/\.hbs$/, '');
        const content = fs.readFileSync(fullPath, 'utf-8');
        this.pageTemplates.set(name, Handlebars.compile(content));
      }
    }
  }

  renderPage(page: PageData): string {
    this.init();

    const templateName = page.frontmatter.template || 'default';
    const layoutName = page.frontmatter.layout || 'default';

    const pageTemplate = this.pageTemplates.get(templateName);
    const pageBody = pageTemplate
      ? pageTemplate({
          title: page.frontmatter.title,
          date: page.frontmatter.date || '',
          tags: page.frontmatter.tags.length
            ? page.frontmatter.tags.join(', ')
            : '',
          content: page.html,
          slug: page.slug,
        })
      : Handlebars.compile(DEFAULT_PAGE_TEMPLATE)({
          title: page.frontmatter.title,
          date: page.frontmatter.date || '',
          tags: page.frontmatter.tags.length
            ? page.frontmatter.tags.join(', ')
            : '',
          content: page.html,
          slug: page.slug,
        });

    const layout = this.layouts.get(layoutName);
    return layout
      ? layout({
          title: page.frontmatter.title,
          body: pageBody,
        })
      : Handlebars.compile(DEFAULT_LAYOUT)({
          title: page.frontmatter.title,
          body: pageBody,
        });
  }

  renderIndex(pages: PageData[], indexLayout?: string, indexTemplate?: string): string {
    this.init();

    const sorted = [...pages].sort((a, b) =>
      b.frontmatter.date.localeCompare(a.frontmatter.date)
    );

    const indexData = sorted.map((p) => ({
      title: p.frontmatter.title,
      date: p.frontmatter.date || '',
      tags: p.frontmatter.tags.length ? p.frontmatter.tags.join(', ') : '',
      slug: p.slug,
    }));

    const itName = indexTemplate || 'index';
    const ilName = indexLayout || 'default';

    const it = this.pageTemplates.get(itName);
    const indexBody = it
      ? it({ pages: indexData })
      : Handlebars.compile(DEFAULT_INDEX_TEMPLATE)({ pages: indexData });

    const layout = this.layouts.get(ilName);
    return layout
      ? layout({ title: 'Blog', body: indexBody })
      : Handlebars.compile(DEFAULT_LAYOUT)({ title: 'Blog', body: indexBody });
  }
}
