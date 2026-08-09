import * as fs from "fs";
import * as path from "path";
import Handlebars from "handlebars";

export function registerPartials(templateDir: string): void {
  const partialsDir = path.join(templateDir, "partials");
  if (!fs.existsSync(partialsDir)) return;

  const files = fs.readdirSync(partialsDir);
  for (const file of files) {
    if (file.endsWith(".hbs") || file.endsWith(".handlebars")) {
      const name = path.basename(file, path.extname(file));
      const content = fs.readFileSync(path.join(partialsDir, file), "utf-8");
      Handlebars.registerPartial(name, content);
    }
  }
}

export function loadTemplate(
  templateDir: string,
  name: string
): HandlebarsTemplateDelegate {
  const templatePath = path.join(templateDir, `${name}.hbs`);

  if (!fs.existsSync(templatePath)) {
    throw new Error(`Template not found: ${templatePath}`);
  }

  const source = fs.readFileSync(templatePath, "utf-8");
  return Handlebars.compile(source);
}

export function renderWithLayout(
  templateDir: string,
  contentHtml: string,
  pageData: Record<string, unknown>,
  layoutName?: string
): string {
  const layout = layoutName || "default";

  try {
    const layoutTemplate = loadTemplate(templateDir, `layouts/${layout}`);
    return layoutTemplate({ ...pageData, content: contentHtml });
  } catch {
    return contentHtml;
  }
}

export function renderTemplate(
  templateDir: string,
  templateName: string,
  data: Record<string, unknown>,
  layoutName?: string
): string {
  const template = loadTemplate(templateDir, templateName);
  const content = template(data);
  return renderWithLayout(templateDir, content, data, layoutName);
}

export function registerHelpers(): void {
  Handlebars.registerHelper("formatDate", (date: string) => {
    if (!date) return "";
    const d = new Date(date);
    if (isNaN(d.getTime())) return date;
    return d.toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  });

  Handlebars.registerHelper("isoDate", (date: string) => {
    if (!date) return "";
    const d = new Date(date);
    if (isNaN(d.getTime())) return "";
    return d.toISOString();
  });

  Handlebars.registerHelper("rfc822Date", (date: string) => {
    if (!date) return "";
    const d = new Date(date);
    if (isNaN(d.getTime())) return "";
    return d.toUTCString();
  });

  Handlebars.registerHelper("encodeURI", (str: string) => {
    return encodeURI(str);
  });
}
