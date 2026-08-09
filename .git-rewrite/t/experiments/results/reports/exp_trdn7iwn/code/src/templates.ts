import Handlebars from "handlebars";
import { promises as fs } from "node:fs";
import path from "node:path";

export interface TemplateEngine {
  /** Render `context` through layout `name` (falls back to "default"). */
  render(name: string, context: Record<string, unknown>): string;
  hasLayout(name: string): boolean;
}

/**
 * Template directory conventions:
 *   templates/layouts/*.hbs   -> named layouts (frontmatter `layout: post` -> layouts/post.hbs)
 *   templates/partials/*.hbs  -> registered as partials by filename
 *   templates/*.hbs           -> also usable as layouts (top-level fallback)
 */
export async function createTemplateEngine(templateDir: string): Promise<TemplateEngine> {
  const hb = Handlebars.create();
  registerHelpers(hb);

  const layouts = new Map<string, Handlebars.TemplateDelegate>();

  const partialsDir = path.join(templateDir, "partials");
  for (const file of await listHbs(partialsDir)) {
    const name = path.basename(file, path.extname(file));
    hb.registerPartial(name, await fs.readFile(file, "utf8"));
  }

  const layoutsDir = path.join(templateDir, "layouts");
  for (const file of await listHbs(layoutsDir)) {
    const name = path.basename(file, path.extname(file));
    layouts.set(name, hb.compile(await fs.readFile(file, "utf8")));
  }
  // Top-level templates act as layouts too (lower precedence).
  for (const file of await listHbs(templateDir)) {
    const name = path.basename(file, path.extname(file));
    if (!layouts.has(name)) {
      layouts.set(name, hb.compile(await fs.readFile(file, "utf8")));
    }
  }

  return {
    hasLayout: (name) => layouts.has(name),
    render(name, context) {
      const template = layouts.get(name) ?? layouts.get("default");
      if (!template) {
        throw new Error(
          `No layout "${name}" and no "default" layout found in ${templateDir}`
        );
      }
      return template(context);
    },
  };
}

function registerHelpers(hb: typeof Handlebars): void {
  hb.registerHelper("formatDate", (date: unknown, fmt?: unknown) => {
    if (!(date instanceof Date)) return "";
    if (fmt === "iso") return date.toISOString();
    return date.toISOString().slice(0, 10);
  });
  hb.registerHelper("eq", (a: unknown, b: unknown) => a === b);
  hb.registerHelper("json", (v: unknown) => JSON.stringify(v));
}

async function listHbs(dir: string): Promise<string[]> {
  try {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    return entries
      .filter((e) => e.isFile() && /\.(hbs|handlebars)$/.test(e.name))
      .map((e) => path.join(dir, e.name))
      .sort();
  } catch {
    return [];
  }
}
