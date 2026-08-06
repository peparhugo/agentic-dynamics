import { readFileSync, existsSync, readdirSync } from "node:fs";
import { join } from "node:path";
import Handlebars from "handlebars";

const compiledTemplates = new Map<string, HandlebarsTemplateDelegate>();
const compiledPartials = new Map<string, HandlebarsTemplateDelegate>();

function loadDirectory(dir: string, map: Map<string, HandlebarsTemplateDelegate>) {
  if (!existsSync(dir)) return;
  for (const file of readdirSync(dir)) {
    if (!file.endsWith(".hbs") && !file.endsWith(".handlebars")) continue;
    const name = file.replace(/\.(hbs|handlebars)$/, "");
    const content = readFileSync(join(dir, file), "utf-8");
    map.set(name, Handlebars.compile(content));
  }
}

export function initTemplates(templatesDir: string): void {
  compiledTemplates.clear();
  compiledPartials.clear();

  const partialsDir = join(templatesDir, "partials");
  loadDirectory(partialsDir, compiledPartials);

  Handlebars.registerHelper("formatDate", (date: string) => {
    if (!date) return "";
    return new Date(date).toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  });

  Handlebars.registerHelper("tagUrl", (tag: string) => `/tags/${encodeURIComponent(String(tag).toLowerCase().replace(/\s+/g, "-"))}/`);

  Handlebars.registerHelper("pageUrl", (url: string) => url);

  for (const [name, fn] of compiledPartials) {
    Handlebars.registerPartial(name, fn);
  }

  const templatesRoot = readdirSync(templatesDir).filter(
    (f) => (f.endsWith(".hbs") || f.endsWith(".handlebars")) && !f.startsWith("_"),
  );
  for (const file of templatesRoot) {
    const name = file.replace(/\.(hbs|handlebars)$/, "");
    compiledTemplates.set(name, Handlebars.compile(readFileSync(join(templatesDir, file), "utf-8")));
  }

  const layoutsDir = join(templatesDir, "layouts");
  if (existsSync(layoutsDir)) {
    for (const file of readdirSync(layoutsDir)) {
      if (!file.endsWith(".hbs") && !file.endsWith(".handlebars")) continue;
      const name = "layout:" + file.replace(/\.(hbs|handlebars)$/, "");
      compiledTemplates.set(name, Handlebars.compile(readFileSync(join(layoutsDir, file), "utf-8")));
    }
  }
}

export function renderTemplate(name: string, data: Record<string, unknown>): string {
  const tpl = compiledTemplates.get(name);
  if (!tpl) throw new Error(`Template "${name}" not found`);
  return tpl(data);
}

export function renderWithLayout(
  templateName: string,
  layoutName: string,
  data: Record<string, unknown>,
): string {
  const body = renderTemplate(templateName, data);
  const layoutKey = "layout:" + layoutName;
  const layoutTpl = compiledTemplates.get(layoutKey);
  if (!layoutTpl) throw new Error(`Layout "${layoutName}" not found`);
  return layoutTpl({ ...data, body });
}

export function templateExists(name: string): boolean {
  return compiledTemplates.has(name) || compiledTemplates.has("layout:" + name);
}
