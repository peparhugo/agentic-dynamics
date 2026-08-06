import fs from "fs";
import path from "path";
import Handlebars from "handlebars";

Handlebars.registerHelper("formatDate", function (date: string) {
  if (!date) return "";
  const d = new Date(date);
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
});

Handlebars.registerHelper("eq", function (a: unknown, b: unknown) {
  return a === b;
});

export interface TemplateEngine {
  render(templateName: string, context: Record<string, unknown>): string;
  renderWithLayout(
    templateName: string,
    layoutName: string,
    context: Record<string, unknown>
  ): string;
}

export function createTemplateEngine(templateDir: string): TemplateEngine {
  const templateCache = new Map<string, HandlebarsTemplateDelegate>();

  function loadDir(dir: string, prefix: string = ""): void {
    if (!fs.existsSync(dir)) return;
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        loadDir(fullPath, prefix + entry.name + "/");
      } else if (entry.isFile() && entry.name.endsWith(".hbs")) {
        const name = prefix + entry.name.replace(/\.hbs$/, "");
        const source = fs.readFileSync(fullPath, "utf-8");
        templateCache.set(name, Handlebars.compile(source));
      }
    }
  }

  function loadPartials(dir: string): void {
    if (!fs.existsSync(dir)) return;
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        loadPartials(fullPath);
      } else if (entry.isFile() && entry.name.endsWith(".hbs")) {
        const name = entry.name.replace(/\.hbs$/, "");
        const source = fs.readFileSync(fullPath, "utf-8");
        Handlebars.registerPartial(name, source);
      }
    }
  }

  const partialsDir = path.join(templateDir, "partials");
  loadPartials(partialsDir);

  loadDir(templateDir);

  function getTemplate(name: string): HandlebarsTemplateDelegate {
    const tpl = templateCache.get(name);
    if (!tpl) {
      throw new Error(
        `Template "${name}" not found. Available: ${[...templateCache.keys()].join(", ")}`
      );
    }
    return tpl;
  }

  return {
    render(templateName: string, context: Record<string, unknown>): string {
      return getTemplate(templateName)(context);
    },

    renderWithLayout(
      templateName: string,
      layoutName: string,
      context: Record<string, unknown>
    ): string {
      const bodyContent = getTemplate(templateName)(context);
      const layoutContext = {
        ...context,
        body: bodyContent,
      };
      return getTemplate(layoutName)(layoutContext);
    },
  };
}
