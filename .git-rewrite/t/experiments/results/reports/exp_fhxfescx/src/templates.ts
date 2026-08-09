import Handlebars from "handlebars";
import { promises as fs } from "node:fs";
import path from "node:path";

export interface TemplateEngine {
  /** Render a named layout (file name without extension) with a context. */
  render(layout: string, context: Record<string, unknown>): string;
  hasLayout(layout: string): boolean;
}

const TEMPLATE_EXTENSIONS = new Set([".hbs", ".handlebars", ".html"]);

async function walk(dir: string): Promise<string[]> {
  const out: string[] = [];
  let entries;
  try {
    entries = await fs.readdir(dir, { withFileTypes: true });
  } catch {
    return out;
  }
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await walk(full)));
    else out.push(full);
  }
  return out;
}

function registerHelpers(hb: typeof Handlebars): void {
  hb.registerHelper("formatDate", (date: unknown, fmt?: unknown) => {
    if (!(date instanceof Date) || isNaN(date.getTime())) return "";
    if (typeof fmt === "string" && fmt === "iso") return date.toISOString();
    return date.toISOString().slice(0, 10);
  });
  hb.registerHelper("eq", (a: unknown, b: unknown) => a === b);
  hb.registerHelper("json", (v: unknown) => JSON.stringify(v));
}

/**
 * Create a template engine from a template directory.
 *
 * Layout resolution:
 *   - `layouts/<name>.hbs` (or .handlebars/.html), falling back to `<name>.hbs`
 *     at the template root.
 * Partials:
 *   - every file under `partials/` is registered as a partial named by its
 *     path relative to `partials/` without extension (e.g. partials/nav.hbs -> {{> nav}}).
 *
 * All templates are compiled once up-front (throughput-oriented): renders are
 * pure function calls with zero I/O.
 */
export async function createTemplateEngine(templateDir: string): Promise<TemplateEngine> {
  const hb = Handlebars.create();
  registerHelpers(hb);

  const layouts = new Map<string, Handlebars.TemplateDelegate>();
  const files = await walk(templateDir);

  for (const file of files) {
    const ext = path.extname(file);
    if (!TEMPLATE_EXTENSIONS.has(ext)) continue;
    const rel = path.relative(templateDir, file).split(path.sep).join("/");
    const name = rel.slice(0, -ext.length);
    const source = await fs.readFile(file, "utf8");

    if (name.startsWith("partials/")) {
      hb.registerPartial(name.slice("partials/".length), source);
    } else if (name.startsWith("layouts/")) {
      layouts.set(name.slice("layouts/".length), hb.compile(source));
    } else {
      // root-level templates also usable as layouts
      if (!layouts.has(name)) layouts.set(name, hb.compile(source));
    }
  }

  return {
    hasLayout: (layout) => layouts.has(layout),
    render(layout, context) {
      const tpl = layouts.get(layout);
      if (!tpl) {
        throw new Error(
          `Layout "${layout}" not found in ${templateDir} (looked in layouts/ and template root)`
        );
      }
      return tpl(context);
    },
  };
}
