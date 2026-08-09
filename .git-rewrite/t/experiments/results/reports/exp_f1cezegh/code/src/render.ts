import Handlebars from "handlebars";
import * as fs from "fs";
import * as path from "path";

export class TemplateEngine {
  private templatesDir: string;
  private partials: Map<string, Handlebars.TemplateDelegate>;
  private layoutTemplate: Handlebars.TemplateDelegate | null;

  constructor(templatesDir: string) {
    this.templatesDir = templatesDir;
    this.partials = new Map();
    this.layoutTemplate = null;
    this.loadPartials();
    this.loadLayout();
    this.registerHelpers();
  }

  private loadPartials(): void {
    const partialsDir = path.join(this.templatesDir, "partials");
    if (!fs.existsSync(partialsDir)) return;

    const files = fs.readdirSync(partialsDir);
    for (const file of files) {
      if (!file.endsWith(".hbs") && !file.endsWith(".handlebars")) continue;
      const name = path.basename(file, path.extname(file));
      const source = fs.readFileSync(path.join(partialsDir, file), "utf-8");
      Handlebars.registerPartial(name, source);
      this.partials.set(name, Handlebars.compile(source));
    }
  }

  private loadLayout(): void {
    const layoutFile = path.join(this.templatesDir, "layout.hbs");
    const altLayoutFile = path.join(this.templatesDir, "layout.handlebars");
    const file = fs.existsSync(layoutFile) ? layoutFile : fs.existsSync(altLayoutFile) ? altLayoutFile : null;

    if (file) {
      const source = fs.readFileSync(file, "utf-8");
      this.layoutTemplate = Handlebars.compile(source);
    }
  }

  private registerHelpers(): void {
    Handlebars.registerHelper("formatDate", (date: Date | string | undefined) => {
      if (!date) return "";
      const d = typeof date === "string" ? new Date(date) : date;
      if (isNaN(d.getTime())) return "";
      return d.toISOString().split("T")[0];
    });

    Handlebars.registerHelper("eq", (a: unknown, b: unknown) => a === b);

    Handlebars.registerHelper("json", (obj: unknown) => {
      return JSON.stringify(obj);
    });
  }

  render(templateName: string, data: Record<string, unknown>): string {
    const content = this.renderContent(templateName, data);

    if (this.layoutTemplate) {
      return this.layoutTemplate({ ...data, body: content, content });
    }

    return content;
  }

  renderString(templateStr: string, data: Record<string, unknown>): string {
    const compiled = Handlebars.compile(templateStr);
    return compiled(data);
  }

  private renderContent(templateName: string, data: Record<string, unknown>): string {
    const file = path.join(this.templatesDir, `${templateName}.hbs`);
    const altFile = path.join(this.templatesDir, `${templateName}.handlebars`);

    const sourcePath = fs.existsSync(file) ? file : fs.existsSync(altFile) ? altFile : null;

    if (!sourcePath) {
      return "";
    }

    const source = fs.readFileSync(sourcePath, "utf-8");
    const compiled = Handlebars.compile(source);
    return compiled(data);
  }

  hasTemplate(name: string): boolean {
    return (
      fs.existsSync(path.join(this.templatesDir, `${name}.hbs`)) ||
      fs.existsSync(path.join(this.templatesDir, `${name}.handlebars`))
    );
  }
}
