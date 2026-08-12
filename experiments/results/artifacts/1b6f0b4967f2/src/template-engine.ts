import Handlebars from 'handlebars';
import fs from 'fs';
import path from 'path';
import { PageTemplateData, IndexTemplateData } from './types';

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

const DEFAULT_PAGE_TEMPLATE = `<main>
  <article>
    <h1>{{title}}</h1>
    {{#if dateFormatted}}<div class="date">{{dateFormatted}}</div>{{/if}}
    {{#if tagsStr}}<div class="tags">Tags: {{tagsStr}}</div>{{/if}}
    {{{content}}}
  </article>
</main>
<footer>
  <a href="index.html">Back to index</a>
</footer>`;

const DEFAULT_INDEX_TEMPLATE = `<main>
  <h1>Pages</h1>
  <ul>
    {{#each pages}}
    <li><a href="{{slug}}.html">{{title}}</a>{{#if dateFormatted}} — {{dateFormatted}}{{/if}}{{#if tagsStr}} [{{tagsStr}}]{{/if}}</li>
    {{/each}}
  </ul>
</main>`;

export class TemplateEngine {
  private hbs: typeof Handlebars;
  private templateDir: string | null;
  private templates: Map<string, Handlebars.TemplateDelegate>;
  private layouts: Map<string, Handlebars.TemplateDelegate>;
  private indexTemplate: Handlebars.TemplateDelegate;

  constructor(templateDir?: string) {
    this.hbs = Handlebars.create();
    this.templateDir = templateDir || null;
    this.templates = new Map();
    this.layouts = new Map();

    this.layouts.set('default', this.hbs.compile(DEFAULT_LAYOUT));
    this.templates.set('default', this.hbs.compile(DEFAULT_PAGE_TEMPLATE));
    this.indexTemplate = this.hbs.compile(DEFAULT_INDEX_TEMPLATE);

    if (this.templateDir && fs.existsSync(this.templateDir)) {
      this.loadPartials();
      this.loadLayouts();
      this.loadTemplates();
    }
  }

  private loadPartials(): void {
    const partialsDir = path.join(this.templateDir!, 'partials');
    if (!fs.existsSync(partialsDir)) return;

    const files = fs.readdirSync(partialsDir);
    for (const file of files) {
      if (file.endsWith('.hbs') || file.endsWith('.handlebars')) {
        const name = path.basename(file, path.extname(file));
        const content = fs.readFileSync(path.join(partialsDir, file), 'utf-8');
        this.hbs.registerPartial(name, content);
      }
    }
  }

  private loadLayouts(): void {
    const layoutsDir = path.join(this.templateDir!, 'layouts');
    if (!fs.existsSync(layoutsDir)) return;

    const files = fs.readdirSync(layoutsDir);
    for (const file of files) {
      if (file.endsWith('.hbs') || file.endsWith('.handlebars')) {
        const name = path.basename(file, path.extname(file));
        const content = fs.readFileSync(path.join(layoutsDir, file), 'utf-8');
        this.layouts.set(name, this.hbs.compile(content));
      }
    }
  }

  private loadTemplates(): void {
    const files = fs.readdirSync(this.templateDir!);
    for (const file of files) {
      if (!(file.endsWith('.hbs') || file.endsWith('.handlebars'))) continue;

      const name = path.basename(file, path.extname(file));
      const content = fs.readFileSync(path.join(this.templateDir!, file), 'utf-8');

      if (name === 'index') {
        this.indexTemplate = this.hbs.compile(content);
      } else {
        this.templates.set(name, this.hbs.compile(content));
      }
    }
  }

  renderPage(data: PageTemplateData, templateName?: string, layoutName?: string): string {
    const tplName = templateName || 'default';
    const layName = layoutName || 'default';

    const template = this.templates.get(tplName) || this.templates.get('default')!;
    const body = template(data);

    const layout = this.layouts.get(layName) || this.layouts.get('default')!;
    return layout({ ...data, body });
  }

  renderIndex(data: IndexTemplateData): string {
    const body = this.indexTemplate(data);
    const layout = this.layouts.get('default')!;
    return layout({ title: data.title, body });
  }
}
