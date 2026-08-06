import Handlebars from "handlebars";
import { promises as fs } from "node:fs";
import path from "node:path";

export interface TemplateEngine {
  /** Render `content` inside the named layout with the given context. */
  renderPage(layout: string, context: Record<string, unknown>): string;
  hasLayout(layout: string): boolean;
}

async function readDirTemplates(dir: string): Promise<Map<string, string>> {
  const out = new Map<string, string>();
  let entries: string[] = [];
  try {
    entries = await fs.readdir(dir);
  } catch {
    return out;
  }
  for (const entry of entries) {
    if (!/\.(hbs|handlebars|html)$/.test(entry)) continue;
    const name = entry.replace(/\.(hbs|handlebars|html)$/, "");
    out.set(name, await fs.readFile(path.join(dir, entry), "utf8"));
  }
  return out;
}

/**
 * Load a template directory:
 *   templates/layouts/*.hbs   -> page layouts (must render `{{{content}}}` somewhere)
 *   templates/partials/*.hbs  -> registered as Handlebars partials by filename
 * Layout files directly in the templates root are also accepted as layouts.
 */
export async function loadTemplates(templateDir: string): Promise<TemplateEngine> {
  const hb = Handlebars.create();

  hb.registerHelper("formatDate", (date: unknown, format?: unknown) => {
    if (!(date instanceof Date) || Number.isNaN(date.getTime())) return "";
    if (format === "rfc822") return date.toUTCString();
    return date.toISOString().slice(0, 10);
  });
  hb.registerHelper("eq", (a: unknown, b: unknown) => a === b);

  const partials = await readDirTemplates(path.join(templateDir, "partials"));
  for (const [name, src] of partials) hb.registerPartial(name, src);

  const layoutSources = new Map<string, string>([
    ...(await readDirTemplates(templateDir)),
    ...(await readDirTemplates(path.join(templateDir, "layouts"))),
  ]);

  const compiled = new Map<string, Handlebars.TemplateDelegate>();
  for (const [name, src] of layoutSources) {
    compiled.set(name, hb.compile(src, { noEscape: false }));
  }

  return {
    hasLayout: (layout) => compiled.has(layout),
    renderPage(layout, context) {
      const template = compiled.get(layout) ?? compiled.get("default");
      if (!template) {
        throw new Error(
          `No layout "${layout}" and no "default" layout found in ${templateDir}`
        );
      }
      return template(context);
    },
  };
}
