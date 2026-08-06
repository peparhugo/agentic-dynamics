import Handlebars from "handlebars";
import { readFileSync, existsSync, readdirSync } from "node:fs";
import { join, extname } from "node:path";

export function createRenderer(templatesDir: string) {
  const partialsDir = join(templatesDir, "partials");

  if (existsSync(partialsDir)) {
    for (const file of readdirSync(partialsDir)) {
      if (extname(file) === ".hbs" || extname(file) === ".handlebars") {
        const name = file.replace(/\.(hbs|handlebars)$/, "");
        const source = readFileSync(join(partialsDir, file), "utf-8");
        Handlebars.registerPartial(name, source);
      }
    }
  }

  function readTemplate(name: string): string {
    for (const ext of [".hbs", ".handlebars"]) {
      const p = join(templatesDir, `${name}${ext}`);
      if (existsSync(p)) return readFileSync(p, "utf-8");
    }
    throw new Error(`Template not found: ${name}`);
  }

  const layoutSrc = readTemplate("layout");
  const layout = Handlebars.compile(layoutSrc);

  function render(templateName: string, data: Record<string, unknown>): string {
    const compiled = Handlebars.compile(readTemplate(templateName));
    const body = compiled(data);

    // If a `layout` key is explicitly passed, use it to distinguish
    // pages that use the layout from pages that skip it (like RSS).
    // Otherwise, wrap every render through the layout, passing body.
    return layout({ ...data, body });
  }

  return { render };
}
