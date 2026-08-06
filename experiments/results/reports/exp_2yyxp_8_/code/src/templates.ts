import Handlebars from "handlebars";
import * as fs from "fs";
import * as path from "path";

export interface TemplateContext {
  page?: Record<string, unknown>;
  pages?: Record<string, unknown>[];
  site?: Record<string, unknown>;
  tags?: Record<string, unknown>[];
  content?: string;
  [key: string]: unknown;
}

export class TemplateEngine {
  private templates: Map<string, Handlebars.TemplateDelegate> = new Map();
  private partials: Map<string, Handlebars.TemplateDelegate> = new Map();
  private rawTemplates: Map<string, string> = new Map();
  private templateDir: string;
  private defaultLayout = "default";

  constructor(templateDir: string) {
    this.templateDir = templateDir;
  }

  load(): void {
    if (!fs.existsSync(this.templateDir)) {
      return;
    }

    this.loadPartials();
    this.loadTemplates();
  }

  private loadPartials(): void {
    const partialsDir = path.join(this.templateDir, "partials");
    if (!fs.existsSync(partialsDir)) return;

    const files = this.readDirRecursive(partialsDir);
    for (const file of files) {
      const name = file
        .replace(partialsDir + path.sep, "")
        .replace(/\.hbs$/, "")
        .replace(/\\/g, "/");
      const source = fs.readFileSync(file, "utf-8");
      this.partials.set(name, Handlebars.compile(source));
      Handlebars.registerPartial(name, source);
    }
  }

  private loadTemplates(): void {
    const files = this.readDirRecursive(this.templateDir);
    for (const file of files) {
      if (file.includes(path.sep + "partials" + path.sep)) continue;
      const name = file
        .replace(this.templateDir + path.sep, "")
        .replace(/\.hbs$/, "")
        .replace(/\\/g, "/");
      const source = fs.readFileSync(file, "utf-8");
      this.templates.set(name, Handlebars.compile(source));
      this.rawTemplates.set(name, source);
    }
  }

  private readDirRecursive(dir: string): string[] {
    const results: string[] = [];
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        results.push(...this.readDirRecursive(fullPath));
      } else if (entry.name.endsWith(".hbs")) {
        results.push(fullPath);
      }
    }
    return results;
  }

  getTemplate(name: string): Handlebars.TemplateDelegate | undefined {
    return this.templates.get(name);
  }

  render(name: string, context: TemplateContext): string {
    const template = this.templates.get(name);
    if (!template) {
      throw new Error(`Template not found: ${name}`);
    }

    const renderedContent = template(context);

    const layoutName = (context.page as Record<string, unknown>)?.["layout"] as string | undefined;
    const layout = layoutName || this.defaultLayout;

    if (layout && layout !== name && this.templates.has(layout)) {
      const layoutTemplate = this.templates.get(layout)!;
      return layoutTemplate({ ...context, content: renderedContent });
    }

    return renderedContent;
  }

  hasTemplate(name: string): boolean {
    return this.templates.has(name);
  }
}
