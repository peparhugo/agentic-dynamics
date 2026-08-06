import fs from "fs";
import path from "path";
import Handlebars from "handlebars";
import { Post, SiteConfig } from "./types";

export interface TemplateContext {
  content: string;
  title: string;
  date?: string;
  tags: string[];
  url: string;
  site: SiteConfig & {
    posts: Post[];
    tags: Array<{ name: string; count: number }>;
  };
}

export function loadTemplates(templateDir: string): {
  templates: Record<string, Handlebars.TemplateDelegate>;
  partials: Record<string, Handlebars.TemplateDelegate>;
  layouts: Record<string, Handlebars.TemplateDelegate>;
} {
  const templates: Record<string, Handlebars.TemplateDelegate> = {};
  const partials: Record<string, Handlebars.TemplateDelegate> = {};
  const layouts: Record<string, Handlebars.TemplateDelegate> = {};

  const layoutDir = path.join(templateDir, "layouts");
  if (fs.existsSync(layoutDir)) {
    const entries = fs.readdirSync(layoutDir);
    for (const entry of entries) {
      if (!entry.endsWith(".hbs")) continue;
      const name = entry.replace(/\.hbs$/, "");
      const src = fs.readFileSync(path.join(layoutDir, entry), "utf-8");
      layouts[name] = Handlebars.compile(src);
    }
  }

  const partialDir = path.join(templateDir, "partials");
  if (fs.existsSync(partialDir)) {
    const entries = fs.readdirSync(partialDir);
    for (const entry of entries) {
      if (!entry.endsWith(".hbs")) continue;
      const name = entry.replace(/\.hbs$/, "");
      const src = fs.readFileSync(path.join(partialDir, entry), "utf-8");
      Handlebars.registerPartial(name, src);
      partials[name] = Handlebars.compile(src);
    }
  }

  const entries = fs.readdirSync(templateDir);
  for (const entry of entries) {
    if (!entry.endsWith(".hbs")) continue;
    const name = entry.replace(/\.hbs$/, "");
    const filePath = path.join(templateDir, entry);
    const src = fs.readFileSync(filePath, "utf-8");
    templates[name] = Handlebars.compile(src);
  }

  return { templates, partials, layouts };
}

export function renderPage(
  templateName: string,
  templates: Record<string, Handlebars.TemplateDelegate>,
  layouts: Record<string, Handlebars.TemplateDelegate>,
  context: TemplateContext
): string {
  const template = templates[templateName];
  if (!template) {
    throw new Error(`Template "${templateName}" not found. Available: ${Object.keys(templates).join(", ")}`);
  }

  const body = template(context);

  const layout = layouts.default || layouts.main || layouts.layout;
  if (layout) {
    return layout({ ...context, body });
  }

  return body;
}

Handlebars.registerHelper("formatDate", (date: string) => {
  if (!date) return "";
  const d = new Date(date);
  if (isNaN(d.getTime())) return date;
  return d.toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });
});

Handlebars.registerHelper("rfc822Date", (date: string) => {
  if (!date) return "";
  const d = new Date(date);
  return d.toUTCString();
});

Handlebars.registerHelper("isoDate", (date: string) => {
  if (!date) return "";
  return new Date(date).toISOString();
});

Handlebars.registerHelper("truncate", (str: string, len: number) => {
  if (!str) return "";
  if (str.length <= len) return str;
  return str.substring(0, len) + "...";
});

Handlebars.registerHelper("encodeURI", (str: string) => {
  return encodeURIComponent(str || "");
});
