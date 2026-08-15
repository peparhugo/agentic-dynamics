import * as fs from 'fs';
import * as path from 'path';
import Handlebars from 'handlebars';

export class TemplateEngine {
  private templatesDir: string;
  private layoutsDir: string;
  private partialsDir: string;
  private cache: Map<string, HandlebarsTemplateDelegate> = new Map();

  constructor(templatesDir: string) {
    this.templatesDir = templatesDir;
    this.layoutsDir = path.join(templatesDir, 'layouts');
    this.partialsDir = path.join(templatesDir, 'partials');
    this.registerPartials();
  }

  private registerPartials(): void {
    if (!fs.existsSync(this.partialsDir)) {
      return;
    }

    const partialFiles = fs.readdirSync(this.partialsDir).filter((f) => f.endsWith('.hbs'));
    for (const file of partialFiles) {
      const partialName = file.replace('.hbs', '');
      const partialContent = fs.readFileSync(path.join(this.partialsDir, file), 'utf-8');
      Handlebars.registerPartial(partialName, partialContent);
    }
  }

  private getTemplate(templatePath: string): HandlebarsTemplateDelegate {
    if (this.cache.has(templatePath)) {
      return this.cache.get(templatePath)!;
    }

    const content = fs.readFileSync(templatePath, 'utf-8');
    const template = Handlebars.compile(content);
    this.cache.set(templatePath, template);
    return template;
  }

  renderTemplate(templatePath: string, data: Record<string, unknown>): string {
    if (!fs.existsSync(templatePath)) {
      throw new Error(`Template not found: ${templatePath}`);
    }

    const template = this.getTemplate(templatePath);
    return template(data);
  }

  renderLayout(layoutName: string, data: Record<string, unknown>): string {
    const layoutPath = path.join(this.layoutsDir, `${layoutName}.hbs`);
    return this.renderTemplate(layoutPath, data);
  }

  renderPageTemplate(
    templateName: string,
    data: Record<string, unknown>,
    layoutName?: string
  ): string {
    const templatePath = path.join(this.templatesDir, `${templateName}.hbs`);
    let html = this.renderTemplate(templatePath, data);

    if (layoutName) {
      const layoutData = {
        ...data,
        body: html,
      };
      html = this.renderLayout(layoutName, layoutData);
    }

    return html;
  }

  getDefaultLayoutPath(): string {
    return path.join(this.layoutsDir, 'default.hbs');
  }

  hasLayout(layoutName: string): boolean {
    const layoutPath = path.join(this.layoutsDir, `${layoutName}.hbs`);
    return fs.existsSync(layoutPath);
  }

  getAvailableTemplates(): string[] {
    if (!fs.existsSync(this.templatesDir)) {
      return [];
    }

    return fs
      .readdirSync(this.templatesDir)
      .filter((f) => f.endsWith('.hbs') && !fs.statSync(path.join(this.templatesDir, f)).isDirectory())
      .map((f) => f.replace('.hbs', ''));
  }

  getAvailableLayouts(): string[] {
    if (!fs.existsSync(this.layoutsDir)) {
      return [];
    }

    return fs
      .readdirSync(this.layoutsDir)
      .filter((f) => f.endsWith('.hbs'))
      .map((f) => f.replace('.hbs', ''));
  }
}
