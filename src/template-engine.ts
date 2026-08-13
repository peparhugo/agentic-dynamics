import fs from 'fs';
import path from 'path';
import Handlebars from 'handlebars';
import { ParsedPage } from './parser';

interface TemplateEngineOptions {
  templateDir: string;
}

interface TemplateData {
  title: string;
  date?: string;
  tags?: string[];
  slug: string;
  html: string;
  body: string;
  [key: string]: any;
}

class TemplateEngine {
  private templateDir: string;
  private layoutsDir: string;
  private partialsDir: string;
  private compiledTemplates: Map<string, Handlebars.TemplateDelegate> = new Map();
  private compiledLayouts: Map<string, Handlebars.TemplateDelegate> = new Map();

  constructor(options: TemplateEngineOptions) {
    this.templateDir = options.templateDir;
    this.layoutsDir = path.join(this.templateDir, 'layouts');
    this.partialsDir = path.join(this.templateDir, 'partials');
    this.registerPartials();
  }

  private registerPartials(): void {
    if (!fs.existsSync(this.partialsDir)) {
      return;
    }

    const partialFiles = fs.readdirSync(this.partialsDir).filter(file => file.endsWith('.hbs'));

    for (const file of partialFiles) {
      const partialName = path.parse(file).name;
      const partialPath = path.join(this.partialsDir, file);
      const partialContent = fs.readFileSync(partialPath, 'utf-8');
      Handlebars.registerPartial(partialName, partialContent);
    }
  }

  private getLayoutPath(layoutName: string): string {
    return path.join(this.layoutsDir, `${layoutName}.hbs`);
  }

  private getTemplatePath(templateName: string): string {
    return path.join(this.templateDir, `${templateName}.hbs`);
  }

  private loadTemplate(templatePath: string): string {
    if (!fs.existsSync(templatePath)) {
      throw new Error(`Template not found: ${templatePath}`);
    }
    return fs.readFileSync(templatePath, 'utf-8');
  }

  private compileTemplate(templateContent: string): Handlebars.TemplateDelegate {
    return Handlebars.compile(templateContent);
  }

  private renderLayout(layoutName: string, content: string, data: TemplateData): string {
    const layoutPath = this.getLayoutPath(layoutName);

    if (!this.compiledLayouts.has(layoutName)) {
      const layoutContent = this.loadTemplate(layoutPath);
      this.compiledLayouts.set(layoutName, this.compileTemplate(layoutContent));
    }

    const layoutTemplate = this.compiledLayouts.get(layoutName)!;
    return layoutTemplate({ ...data, body: new Handlebars.SafeString(content) });
  }

  private renderTemplate(templateName: string, data: TemplateData): string {
    const templatePath = this.getTemplatePath(templateName);

    if (!this.compiledTemplates.has(templateName)) {
      const templateContent = this.loadTemplate(templatePath);
      this.compiledTemplates.set(templateName, this.compileTemplate(templateContent));
    }

    const template = this.compiledTemplates.get(templateName)!;
    return template(data);
  }

  renderPage(page: ParsedPage, templateName?: string, layoutName?: string): string {
    const data: TemplateData = {
      ...page.frontmatter,
      slug: page.slug,
      html: page.html,
      body: page.html,
      title: page.frontmatter.title,
      date: page.frontmatter.date,
      tags: page.frontmatter.tags,
    };

    let renderedContent: string;

    if (templateName) {
      renderedContent = this.renderTemplate(templateName, data);
    } else {
      renderedContent = page.html;
    }

    if (layoutName) {
      data.body = renderedContent;
      renderedContent = this.renderLayout(layoutName, renderedContent, data);
    }

    return renderedContent;
  }

  hasTemplate(templateName: string): boolean {
    const templatePath = this.getTemplatePath(templateName);
    return fs.existsSync(templatePath);
  }

  hasLayout(layoutName: string): boolean {
    const layoutPath = this.getLayoutPath(layoutName);
    return fs.existsSync(layoutPath);
  }
}

export { TemplateEngine, TemplateEngineOptions, TemplateData };
