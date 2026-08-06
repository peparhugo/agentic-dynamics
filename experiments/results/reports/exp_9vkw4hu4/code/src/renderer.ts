import Handlebars from "handlebars";
import path from "node:path";
import fs from "node:fs";

export class Renderer {
  private partialsDir: string;
  private layoutsDir: string;
  private pagesDir: string;

  constructor(templateDir: string) {
    this.partialsDir = path.join(templateDir, "partials");
    this.layoutsDir = path.join(templateDir, "layouts");
    this.pagesDir = path.join(templateDir, "pages");
  }

  registerPartials(): void {
    if (!fs.existsSync(this.partialsDir)) return;
    for (const file of fs.readdirSync(this.partialsDir)) {
      if (!file.endsWith(".hbs") && !file.endsWith(".handlebars")) continue;
      const name = path.basename(file, path.extname(file));
      const content = fs.readFileSync(path.join(this.partialsDir, file), "utf-8");
      Handlebars.registerPartial(name, content);
    }
  }

  renderPage(templateName: string, data: Record<string, unknown>): string {
    const pagePath = path.join(this.pagesDir, `${templateName}.hbs`);
    if (!fs.existsSync(pagePath)) {
      throw new Error(`Page template not found: ${pagePath}`);
    }
    const pageSrc = fs.readFileSync(pagePath, "utf-8");
    const template = Handlebars.compile(pageSrc);
    const body = template(data);

    const layout = (data.layout as string) || "default";
    const layoutPath = path.join(this.layoutsDir, `${layout}.hbs`);
    if (fs.existsSync(layoutPath)) {
      const layoutSrc = fs.readFileSync(layoutPath, "utf-8");
      const layoutTemplate = Handlebars.compile(layoutSrc);
      return layoutTemplate({ ...data, body });
    }

    return body;
  }

  renderString(template: string, data: Record<string, unknown>): string {
    const compiled = Handlebars.compile(template);
    return compiled(data);
  }
}
