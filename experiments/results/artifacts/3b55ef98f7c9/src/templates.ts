import Handlebars from 'handlebars';
import fs from 'fs';
import path from 'path';
import { Page } from './types';

const DEFAULT_PAGE_TEMPLATE = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{title}}</title>
</head>
<body>
  <header>
    <nav><a href="index.html">Home</a></nav>
  </header>
  <main>
    <article>
      <h1>{{title}}</h1>
      {{#if date}}<time datetime="{{date}}">{{date}}</time>{{/if}}
      {{#if tagsStr}}<p>Tags: {{tagsStr}}</p>{{/if}}
      <div>{{{body}}}</div>
    </article>
  </main>
</body>
</html>`;

const DEFAULT_INDEX_TEMPLATE = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Index</title>
</head>
<body>
  <header>
    <h1>All Pages</h1>
  </header>
  <main>
    <ul>
{{#each pages}}      <li>
        <a href="{{slug}}.html">{{title}}</a>
        {{#if date}}<span>{{date}}</span>{{/if}}
        {{#if tagsStr}}<span>Tags: {{tagsStr}}</span>{{/if}}
      </li>
{{/each}}
    </ul>
  </main>
</body>
</html>`;

const DEFAULT_LAYOUT = '{{{body}}}';

export interface TemplateEngineOptions {
  templatesDir: string;
}

export class TemplateEngine {
  private pageTemplate: Handlebars.TemplateDelegate;
  private indexTemplate: Handlebars.TemplateDelegate;
  private layoutTemplate: Handlebars.TemplateDelegate;
  private customTemplates: Map<string, Handlebars.TemplateDelegate> = new Map();
  private customLayouts: Map<string, Handlebars.TemplateDelegate> = new Map();
  private initialized: boolean = false;

  constructor() {
    this.pageTemplate = Handlebars.compile(DEFAULT_PAGE_TEMPLATE, { noEscape: true });
    this.indexTemplate = Handlebars.compile(DEFAULT_INDEX_TEMPLATE, { noEscape: true });
    this.layoutTemplate = Handlebars.compile(DEFAULT_LAYOUT);
  }

  init(templatesDir: string): void {
    if (!fs.existsSync(templatesDir)) {
      return;
    }

    const partialsDir = path.join(templatesDir, 'partials');
    if (fs.existsSync(partialsDir)) {
      const partialFiles = fs.readdirSync(partialsDir);
      for (const file of partialFiles) {
        if (file.endsWith('.hbs')) {
          const name = path.basename(file, '.hbs');
          const content = fs.readFileSync(path.join(partialsDir, file), 'utf-8');
          Handlebars.registerPartial(name, content);
        }
      }
    }

    const layoutsDir = path.join(templatesDir, 'layouts');
    if (fs.existsSync(layoutsDir)) {
      const layoutFiles = fs.readdirSync(layoutsDir);
      for (const file of layoutFiles) {
        if (file.endsWith('.hbs')) {
          const name = path.basename(file, '.hbs');
          const content = fs.readFileSync(path.join(layoutsDir, file), 'utf-8');
          this.customLayouts.set(name, Handlebars.compile(content));
        }
      }
    }

    const entries = fs.readdirSync(templatesDir);
    for (const entry of entries) {
      const fullPath = path.join(templatesDir, entry);
      const stat = fs.statSync(fullPath);
      if (stat.isFile() && entry.endsWith('.hbs')) {
        const name = path.basename(entry, '.hbs');
        const content = fs.readFileSync(fullPath, 'utf-8');
        this.customTemplates.set(name, Handlebars.compile(content));
      }
    }

    this.initialized = true;
  }

  renderPage(page: Page): string {
    const templateName = page.frontmatter.template;
    const template = templateName ? this.customTemplates.get(templateName) : undefined;
    const compiledTemplate = template || this.pageTemplate;

    const { title, date, tags } = page.frontmatter;
    const tagsStr = tags ? tags.join(', ') : '';

    const pageHtml = compiledTemplate({
      title,
      date: date || null,
      tagsStr: tagsStr || null,
      body: page.html,
    });

    const layoutName = page.frontmatter.layout;
    const layout = layoutName ? this.customLayouts.get(layoutName) : undefined;
    const compiledLayout = layout || this.layoutTemplate;

    return compiledLayout({
      title,
      date: date || null,
      tagsStr: tagsStr || null,
      body: pageHtml,
      content: page.html,
      pages: [],
    });
  }

  renderIndex(pages: Page[]): string {
    const items = pages.map((p) => ({
      title: p.frontmatter.title,
      date: p.frontmatter.date || null,
      tagsStr: p.frontmatter.tags ? p.frontmatter.tags.join(', ') : null,
      slug: p.slug,
    }));

    return this.indexTemplate({ pages: items });
  }
}
