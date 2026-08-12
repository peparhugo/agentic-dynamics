import * as fs from 'fs';
import * as path from 'path';
import Handlebars from 'handlebars';
import { Page } from './types';

export interface TemplateEngineOptions {
  templatesDir: string;
}

export class TemplateEngine {
  private templatesDir: string;
  private layoutsDir: string;
  private partialsDir: string;
  private compiledTemplates: Map<string, HandlebarsTemplateDelegate>;
  private compiledLayouts: Map<string, HandlebarsTemplateDelegate>;

  constructor(options: TemplateEngineOptions) {
    this.templatesDir = options.templatesDir;
    this.layoutsDir = path.join(this.templatesDir, 'layouts');
    this.partialsDir = path.join(this.templatesDir, 'partials');
    this.compiledTemplates = new Map();
    this.compiledLayouts = new Map();
    this.loadPartials();
  }

  private loadPartials(): void {
    if (!fs.existsSync(this.partialsDir)) return;

    const files = fs.readdirSync(this.partialsDir).filter((f) => f.endsWith('.hbs'));
    for (const file of files) {
      const name = path.basename(file, '.hbs');
      const source = fs.readFileSync(path.join(this.partialsDir, file), 'utf-8');
      Handlebars.registerPartial(name, source);
    }
  }

  private loadTemplate(name: string): HandlebarsTemplateDelegate {
    const filePath = path.join(this.templatesDir, `${name}.hbs`);
    if (!fs.existsSync(filePath)) {
      throw new Error(`Template not found: ${filePath}`);
    }
    const source = fs.readFileSync(filePath, 'utf-8');
    return Handlebars.compile(source);
  }

  private loadLayout(name: string): HandlebarsTemplateDelegate {
    const filePath = path.join(this.layoutsDir, `${name}.hbs`);
    if (!fs.existsSync(filePath)) {
      throw new Error(`Layout not found: ${filePath}`);
    }
    const source = fs.readFileSync(filePath, 'utf-8');
    return Handlebars.compile(source);
  }

  private getTemplate(name: string): HandlebarsTemplateDelegate {
    if (!this.compiledTemplates.has(name)) {
      this.compiledTemplates.set(name, this.loadTemplate(name));
    }
    return this.compiledTemplates.get(name)!;
  }

  private getLayout(name: string): HandlebarsTemplateDelegate {
    if (!this.compiledLayouts.has(name)) {
      this.compiledLayouts.set(name, this.loadLayout(name));
    }
    return this.compiledLayouts.get(name)!;
  }

  hasTemplate(name: string): boolean {
    return fs.existsSync(path.join(this.templatesDir, `${name}.hbs`));
  }

  hasLayout(name: string): boolean {
    return fs.existsSync(path.join(this.layoutsDir, `${name}.hbs`));
  }

  hasIndex(): boolean {
    return fs.existsSync(path.join(this.templatesDir, 'index.hbs'));
  }

  render(page: Page, templateName?: string, layoutName?: string): string {
    const tplName = templateName || 'default';
    const template = this.getTemplate(tplName);
    const templateHtml = template(page);

    const lytName = layoutName || 'default';
    if (this.hasLayout(lytName)) {
      const layout = this.getLayout(lytName);
      return layout({ ...page, body: templateHtml });
    }

    return templateHtml;
  }

  renderIndex(pages: Page[]): string {
    const template = this.getTemplate('index');
    return template({ pages });
  }
}
