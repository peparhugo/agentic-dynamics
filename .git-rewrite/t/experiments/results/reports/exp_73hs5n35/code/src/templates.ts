import fs from "node:fs/promises";
import path from "node:path";
import Handlebars from "handlebars";

export interface TemplateEngine {
  /** Render named layout (file basename without .hbs) with a context. */
  render(layout: string, context: Record<string, unknown>): string;
  has(layout: string): boolean;
  layouts(): string[];
}

function registerHelpers(hb: typeof Handlebars): void {
  hb.registerHelper("formatDate", (date: unknown, fmt?: unknown) => {
    if (!(date instanceof Date) || Number.isNaN(date.getTime())) return "";
    if (fmt === "iso") return date.toISOString();
    return date.toISOString().slice(0, 10);
  });
  hb.registerHelper("limit", (arr: unknown, n: unknown) =>
    Array.isArray(arr) ? arr.slice(0, Number(n)) : [],
  );
  hb.registerHelper("eq", (a: unknown, b: unknown) => a === b);
}

/**
 * Load a Handlebars template directory:
 *  - `<dir>/*.hbs`           -> layouts, addressable by basename
 *  - `<dir>/partials/*.hbs`  -> partials, addressable as {{> name}}
 */
export async function loadTemplates(templateDir: string): Promise<TemplateEngine> {
  const hb = Handlebars.create();
  registerHelpers(hb);

  const compiled = new Map<string, Handlebars.TemplateDelegate>();

  const entries = await fs.readdir(templateDir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.isFile() && entry.name.endsWith(".hbs")) {
      const src = await fs.readFile(path.join(templateDir, entry.name), "utf8");
      compiled.set(entry.name.replace(/\.hbs$/, ""), hb.compile(src));
    }
  }

  const partialsDir = path.join(templateDir, "partials");
  try {
    for (const name of await fs.readdir(partialsDir)) {
      if (!name.endsWith(".hbs")) continue;
      const src = await fs.readFile(path.join(partialsDir, name), "utf8");
      hb.registerPartial(name.replace(/\.hbs$/, ""), src);
    }
  } catch (err: unknown) {
    if ((err as NodeJS.ErrnoException).code !== "ENOENT") throw err;
  }

  if (!compiled.has("default")) {
    throw new Error(`Template directory ${templateDir} must contain a default.hbs layout`);
  }

  return {
    render(layout, context) {
      const tpl = compiled.get(layout);
      if (!tpl) throw new Error(`Unknown layout "${layout}" (available: ${[...compiled.keys()].join(", ")})`);
      return tpl(context);
    },
    has: (layout) => compiled.has(layout),
    layouts: () => [...compiled.keys()].sort(),
  };
}

export { Handlebars };
