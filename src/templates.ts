import fs from 'fs';
import path from 'path';
import Handlebars from 'handlebars';

export interface TemplateConfig {
  templatesDir: string;
  layoutsDir: string;
  partialsDir: string;
  defaultLayout?: string;
  defaultTemplate?: string;
}

type TemplateFunction = (context: Record<string, unknown>) => string;

export class TemplateEngine {
  private config: TemplateConfig;
  private templates: Map<string, TemplateFunction> = new Map();
  private layouts: Map<string, TemplateFunction> = new Map();
  private partialsLoaded: boolean = false;

  constructor(config: TemplateConfig) {
    this.config = {
      templatesDir: config.templatesDir || './templates',
      layoutsDir: config.layoutsDir || './templates/layouts',
      partialsDir: config.partialsDir || './templates/partials',
      defaultLayout: config.defaultLayout || 'default',
      defaultTemplate: config.defaultTemplate || 'page',
    };
  }

  private loadPartials(): void {
    if (this.partialsLoaded) return;

    if (!fs.existsSync(this.config.partialsDir)) {
      this.partialsLoaded = true;
      return;
    }

    const partialsFiles = fs.readdirSync(this.config.partialsDir);
    for (const file of partialsFiles) {
      if (file.endsWith('.hbs')) {
        const partialPath = path.join(this.config.partialsDir, file);
        const partialContent = fs.readFileSync(partialPath, 'utf-8');
        const partialName = file.replace(/\.hbs$/, '');
        Handlebars.registerPartial(partialName, partialContent);
      }
    }

    this.partialsLoaded = true;
  }

  getTemplatePath(templateName: string): string {
    return path.join(this.config.templatesDir, `${templateName}.hbs`);
  }

  getLayoutPath(layoutName: string): string {
    return path.join(this.config.layoutsDir, `${layoutName}.hbs`);
  }

  loadTemplate(templateName: string): TemplateFunction {
    if (this.templates.has(templateName)) {
      return this.templates.get(templateName)!;
    }

    this.loadPartials();

    const templatePath = this.getTemplatePath(templateName);
    if (!fs.existsSync(templatePath)) {
      throw new Error(`Template not found: ${templatePath}`);
    }

    const templateContent = fs.readFileSync(templatePath, 'utf-8');
    const compiled = Handlebars.compile(templateContent);
    this.templates.set(templateName, compiled);
    return compiled;
  }

  loadLayout(layoutName: string): TemplateFunction {
    if (this.layouts.has(layoutName)) {
      return this.layouts.get(layoutName)!;
    }

    this.loadPartials();

    const layoutPath = this.getLayoutPath(layoutName);
    if (!fs.existsSync(layoutPath)) {
      throw new Error(`Layout not found: ${layoutPath}`);
    }

    const layoutContent = fs.readFileSync(layoutPath, 'utf-8');
    const compiled = Handlebars.compile(layoutContent);
    this.layouts.set(layoutName, compiled);
    return compiled;
  }

  renderTemplate(
    templateName: string,
    context: Record<string, unknown>
  ): string {
    const template = this.loadTemplate(templateName);
    return template(context);
  }

  renderLayout(
    layoutName: string,
    context: Record<string, unknown>
  ): string {
    const layout = this.loadLayout(layoutName);
    return layout(context);
  }

  renderPageWithLayout(
    pageContent: string,
    layoutName: string,
    context: Record<string, unknown>
  ): string {
    const layout = this.loadLayout(layoutName);
    return layout({
      ...context,
      body: pageContent,
    });
  }

  hasTemplate(templateName: string): boolean {
    const templatePath = this.getTemplatePath(templateName);
    return fs.existsSync(templatePath);
  }

  hasLayout(layoutName: string): boolean {
    const layoutPath = this.getLayoutPath(layoutName);
    return fs.existsSync(layoutPath);
  }

  registerHelper(name: string, fn: (...args: unknown[]) => unknown): void {
    Handlebars.registerHelper(name, fn);
  }

  getTemplatesDir(): string {
    return this.config.templatesDir;
  }
}

export function createTemplateEngine(config: Partial<TemplateConfig> = {}): TemplateEngine {
  return new TemplateEngine({
    templatesDir: './templates',
    layoutsDir: './templates/layouts',
    partialsDir: './templates/partials',
    ...config,
  });
}
