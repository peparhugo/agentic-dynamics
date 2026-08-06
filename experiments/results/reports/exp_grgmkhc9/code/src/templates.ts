import fs from "node:fs";
import path from "node:path";
import Handlebars from "handlebars";
import { TemplateContext, SiteConfig } from "./types";

export function createTemplateEngine(templateDir: string, _config: SiteConfig): HandlebarsTemplateEngine {
  return new HandlebarsTemplateEngine(templateDir);
}

export class HandlebarsTemplateEngine {
  private templates = new Map<string, Handlebars.TemplateDelegate>();
  private templateDir: string;
  private layoutDir: string;
  private partialDir: string;

  constructor(templateDir: string) {
    this.templateDir = templateDir;
    this.layoutDir = path.join(templateDir, "layouts");
    this.partialDir = path.join(templateDir, "partials");
    this.loadPartials();
    this.loadLayouts();
  }

  private loadPartials() {
    if (!fs.existsSync(this.partialDir)) return;
    const files = fs.readdirSync(this.partialDir);
    for (const file of files) {
      if (file.endsWith(".hbs") || file.endsWith(".handlebars")) {
        const name = path.basename(file, path.extname(file));
        const source = fs.readFileSync(path.join(this.partialDir, file), "utf-8");
        Handlebars.registerPartial(name, source);
      }
    }
  }

  private loadLayouts() {
    if (!fs.existsSync(this.layoutDir)) return;
    const files = fs.readdirSync(this.layoutDir);
    for (const file of files) {
      if (file.endsWith(".hbs") || file.endsWith(".handlebars")) {
        const name = path.basename(file, path.extname(file));
        const source = fs.readFileSync(path.join(this.layoutDir, file), "utf-8");
        this.templates.set(`layout:${name}`, Handlebars.compile(source));
      }
    }
  }

  private loadTemplate(name: string): Handlebars.TemplateDelegate {
    const cached = this.templates.get(name);
    if (cached) return cached;

    const filePath = path.join(this.templateDir, `${name}.hbs`);
    if (!fs.existsSync(filePath)) {
      const altPath = path.join(this.templateDir, `${name}.handlebars`);
      if (!fs.existsSync(altPath)) {
        throw new Error(`Template not found: ${name}`);
      }
      const source = fs.readFileSync(altPath, "utf-8");
      const compiled = Handlebars.compile(source);
      this.templates.set(name, compiled);
      return compiled;
    }
    const source = fs.readFileSync(filePath, "utf-8");
    const compiled = Handlebars.compile(source);
    this.templates.set(name, compiled);
    return compiled;
  }

  render(templateName: string, context: TemplateContext): string {
    const contentTemplate = this.loadTemplate(templateName);
    const contentHtml = contentTemplate(context);

    const layoutName = context.page?.frontmatter?.layout ?? "default";
    const layoutKey = `layout:${layoutName}`;
    const layoutTemplate = this.templates.get(layoutKey);

    if (layoutTemplate) {
      const layoutContext = { ...context, body: contentHtml };
      return layoutTemplate(layoutContext);
    }

    return contentHtml;
  }

  renderString(template: string, context: TemplateContext): string {
    const compiled = Handlebars.compile(template);
    return compiled(context);
  }

  clearCache() {
    this.templates.clear();
    this.loadLayouts();
  }
}
