import Handlebars from "handlebars";
import fs from "node:fs";
import path from "node:path";

export type Layouts = Map<string, Handlebars.TemplateDelegate>;

export interface TemplateSet {
  hbs: typeof Handlebars;
  layouts: Layouts;
  /** render a page body through the named layout ("default" fallback) */
  renderLayout(name: string, context: Record<string, unknown>): string;
  has(name: string): boolean;
}

/**
 * Template dir convention:
 *   templates/*.hbs          -> layouts (default.hbs, post.hbs, tag.hbs, index.hbs, ...)
 *   templates/partials/*.hbs -> registered as partials by filename
 */
export function loadTemplates(templateDir: string): TemplateSet {
  const hbs = Handlebars.create();
  registerHelpers(hbs);

  const partialsDir = path.join(templateDir, "partials");
  if (fs.existsSync(partialsDir)) {
    for (const f of fs.readdirSync(partialsDir).filter((f) => f.endsWith(".hbs"))) {
      const name = path.basename(f, ".hbs");
      hbs.registerPartial(name, fs.readFileSync(path.join(partialsDir, f), "utf8"));
    }
  }

  const layouts: Layouts = new Map();
  if (fs.existsSync(templateDir)) {
    for (const f of fs.readdirSync(templateDir).filter((f) => f.endsWith(".hbs"))) {
      const name = path.basename(f, ".hbs");
      layouts.set(name, hbs.compile(fs.readFileSync(path.join(templateDir, f), "utf8")));
    }
  }

  return {
    hbs,
    layouts,
    has: (name) => layouts.has(name),
    renderLayout(name, context) {
      const tpl = layouts.get(name) ?? layouts.get("default");
      if (!tpl) throw new Error(`No layout "${name}" and no default.hbs in ${templateDir}`);
      return tpl(context);
    },
  };
}

export function registerHelpers(hbs: typeof Handlebars): void {
  hbs.registerHelper("formatDate", (d: unknown, fmt?: unknown) => {
    const date = d instanceof Date ? d : d ? new Date(String(d)) : null;
    if (!date || isNaN(date.getTime())) return "";
    if (fmt === "iso") return date.toISOString();
    return date.toISOString().slice(0, 10); // YYYY-MM-DD
  });
  hbs.registerHelper("eq", (a: unknown, b: unknown) => a === b);
  hbs.registerHelper("join", (arr: unknown, sep: unknown) =>
    Array.isArray(arr) ? arr.join(typeof sep === "string" ? sep : ", ") : ""
  );
}
