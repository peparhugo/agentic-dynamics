import fs from 'fs';
import path from 'path';
import Handlebars from 'handlebars';

export interface PageData {
  title: string;
  date: string;
  tags: string[];
  content: string;
  slug: string;
  layout?: string;
  template?: string;
}

export class TemplateEngine {
  private templatesDir: string;
  private layoutsDir: string;
  private partialsDir: string;
  private compiledLayouts: Map<string, HandlebarsTemplateDelegate>;
  private compiledTemplates: Map<string, HandlebarsTemplateDelegate>;
  public initialized: boolean;

  constructor(templatesDir: string) {
    this.templatesDir = templatesDir;
    this.layoutsDir = path.join(templatesDir, 'layouts');
    this.partialsDir = path.join(templatesDir, 'partials');
    this.compiledLayouts = new Map();
    this.compiledTemplates = new Map();
    this.initialized = fs.existsSync(templatesDir);

    if (this.initialized) {
      this.loadPartials();
      this.loadLayouts();
      this.loadTemplates();
    }
  }

  private loadPartials(): void {
    if (!fs.existsSync(this.partialsDir)) return;
    const files = fs.readdirSync(this.partialsDir);
    for (const file of files) {
      if (file.endsWith('.hbs')) {
        const name = path.basename(file, '.hbs');
        const content = fs.readFileSync(path.join(this.partialsDir, file), 'utf-8');
        Handlebars.registerPartial(name, content);
      }
    }
  }

  private loadLayouts(): void {
    if (!fs.existsSync(this.layoutsDir)) return;
    const files = fs.readdirSync(this.layoutsDir);
    for (const file of files) {
      if (file.endsWith('.hbs')) {
        const name = path.basename(file, '.hbs');
        const content = fs.readFileSync(path.join(this.layoutsDir, file), 'utf-8');
        this.compiledLayouts.set(name, Handlebars.compile(content));
      }
    }
  }

  private loadTemplates(): void {
    const files = fs.readdirSync(this.templatesDir);
    for (const file of files) {
      if (file.endsWith('.hbs')) {
        const name = path.basename(file, '.hbs');
        const content = fs.readFileSync(path.join(this.templatesDir, file), 'utf-8');
        this.compiledTemplates.set(name, Handlebars.compile(content));
      }
    }
  }

  private getLayout(name?: string): HandlebarsTemplateDelegate | null {
    const layoutName = name || 'default';
    return this.compiledLayouts.get(layoutName) || null;
  }

  private getTemplate(name?: string): HandlebarsTemplateDelegate | null {
    if (!name) return null;
    return this.compiledTemplates.get(name) || null;
  }

  render(data: PageData): string | null {
    if (!this.initialized) return null;

    let bodyHtml: string;

    const pageTemplate = this.getTemplate(data.template);
    if (pageTemplate) {
      bodyHtml = pageTemplate(data);
    } else {
      bodyHtml = data.content;
    }

    const layout = this.getLayout(data.layout);
    if (layout) {
      return layout({ ...data, body: bodyHtml });
    }

    return bodyHtml;
  }

  renderIndex(pages: PageData[]): string | null {
    if (!this.initialized) return null;

    const layout = this.getLayout('index') || this.getLayout('default');
    if (!layout) return null;

    const listItems = pages
      .map(
        (page) =>
          `<li><a href="${page.slug}.html">${page.title}</a>${
            page.date ? ` <time>${page.date}</time>` : ''
          }${
            page.tags.length ? ` [${page.tags.join(', ')}]` : ''
          }</li>`
      )
      .join('\n');

    const content = `<h1>All Pages</h1>\n<ul>\n${listItems}\n</ul>`;

    return layout({ body: content, content, title: 'All Pages', tags: [], date: '' });
  }
}
