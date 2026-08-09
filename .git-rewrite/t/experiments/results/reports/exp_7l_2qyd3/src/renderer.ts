import Handlebars from "handlebars";
import fs from "node:fs";
import path from "node:path";

export interface TemplateContext {
  [key: string]: unknown;
  page?: unknown;
  pages?: unknown[];
  site?: unknown;
  tags?: unknown;
}

export function loadPartials(partialsDir: string): void {
  if (!fs.existsSync(partialsDir)) return;
  const entries = fs.readdirSync(partialsDir);
  for (const entry of entries) {
    const fpath = path.join(partialsDir, entry);
    if (!fpath.endsWith(".hbs")) continue;
    const name = path.basename(entry, ".hbs");
    const src = fs.readFileSync(fpath, "utf-8");
    Handlebars.registerPartial(name, src);
  }
}

export function compileTemplate(templateDir: string, templateName: string): HandlebarsTemplateDelegate {
  const fpath = path.join(templateDir, `${templateName}.hbs`);
  if (!fs.existsSync(fpath)) {
    throw new Error(`Template not found: ${fpath}`);
  }
  const src = fs.readFileSync(fpath, "utf-8");
  return Handlebars.compile(src);
}

export function renderPage(
  content: string,
  layout: HandlebarsTemplateDelegate | null,
  template: HandlebarsTemplateDelegate,
  context: TemplateContext
): string {
  const body = template(context);
  if (layout) {
    return layout({ ...context, body });
  }
  return body;
}

export function compileLayout(templateDir: string, layoutName: string): HandlebarsTemplateDelegate | null {
  const fpath = path.join(templateDir, `${layoutName}.hbs`);
  if (!fs.existsSync(fpath)) return null;
  const src = fs.readFileSync(fpath, "utf-8");
  return Handlebars.compile(src);
}
