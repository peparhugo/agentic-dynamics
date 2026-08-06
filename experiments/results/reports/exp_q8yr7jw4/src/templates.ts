import Handlebars from "handlebars";
import fs from "node:fs";
import path from "node:path";

/**
 * Template engine wrapping Handlebars.
 *
 * Directory convention:
 *   templates/
 *     index.hbs, post.hbs, tag.hbs   -- page templates
 *     layouts/*.hbs                  -- layouts; page output is injected as {{{body}}}
 *     partials/*.hbs                 -- registered as partials by filename
 */
export class TemplateEngine {
  private hbs = Handlebars.create();
  private pages = new Map<string, Handlebars.TemplateDelegate>();
  private layouts = new Map<string, Handlebars.TemplateDelegate>();

  constructor(private templateDir: string) {
    this.registerHelpers();
    this.load();
  }

  /** Reload all templates from disk (used by the dev server on changes). */
  reload(): void {
    this.hbs = Handlebars.create();
    this.pages.clear();
    this.layouts.clear();
    this.registerHelpers();
    this.load();
  }

  private registerHelpers(): void {
    this.hbs.registerHelper("formatDate", (date: unknown, fmt?: unknown) => {
      if (!(date instanceof Date)) return "";
      if (fmt === "iso") return date.toISOString();
      return date.toISOString().slice(0, 10);
    });
    this.hbs.registerHelper("eq", (a: unknown, b: unknown) => a === b);
    this.hbs.registerHelper("join", (arr: unknown, sep: unknown) =>
      Array.isArray(arr) ? arr.join(typeof sep === "string" ? sep : ", ") : ""
    );
  }

  private load(): void {
    if (!fs.existsSync(this.templateDir)) {
      throw new Error(`Template directory not found: ${this.templateDir}`);
    }
    for (const entry of fs.readdirSync(this.templateDir, { withFileTypes: true })) {
      const full = path.join(this.templateDir, entry.name);
      if (entry.isFile() && entry.name.endsWith(".hbs")) {
        this.pages.set(path.basename(entry.name, ".hbs"), this.hbs.compile(fs.readFileSync(full, "utf8")));
      } else if (entry.isDirectory() && entry.name === "partials") {
        for (const f of fs.readdirSync(full).filter((f) => f.endsWith(".hbs"))) {
          this.hbs.registerPartial(path.basename(f, ".hbs"), fs.readFileSync(path.join(full, f), "utf8"));
        }
      } else if (entry.isDirectory() && entry.name === "layouts") {
        for (const f of fs.readdirSync(full).filter((f) => f.endsWith(".hbs"))) {
          this.layouts.set(path.basename(f, ".hbs"), this.hbs.compile(fs.readFileSync(path.join(full, f), "utf8")));
        }
      }
    }
  }

  hasPage(name: string): boolean {
    return this.pages.has(name);
  }

  /**
   * Render a page template, then wrap it in a layout (if one is given and exists).
   * The rendered page is exposed to the layout as {{{body}}}.
   */
  render(page: string, context: Record<string, unknown>, layout?: string): string {
    const tpl = this.pages.get(page);
    if (!tpl) throw new Error(`Template not found: ${page}.hbs in ${this.templateDir}`);
    const body = tpl(context);
    const layoutName = layout ?? "default";
    const layoutTpl = this.layouts.get(layoutName);
    if (layout && !layoutTpl) throw new Error(`Layout not found: layouts/${layout}.hbs`);
    if (!layoutTpl) return body;
    return layoutTpl({ ...context, body });
  }
}
