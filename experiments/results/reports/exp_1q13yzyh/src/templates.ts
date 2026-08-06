import fs from "node:fs/promises";
import path from "node:path";
import Handlebars from "handlebars";

/**
 * Template directory convention:
 *   templates/
 *     layouts/    -> layouts (default.hbs, post.hbs, ...); receive {{{content}}}
 *     partials/   -> registered as partials by filename (header.hbs -> {{> header}})
 *     index.hbs   -> site index page
 *     tag.hbs     -> per-tag index page (optional; falls back to index.hbs)
 */
export class TemplateEngine {
  private hb = Handlebars.create();
  private layouts = new Map<string, Handlebars.TemplateDelegate>();
  private pages = new Map<string, Handlebars.TemplateDelegate>();

  private constructor() {
    this.hb.registerHelper("formatDate", (date: unknown, fmt?: unknown) => {
      const d = date instanceof Date ? date : new Date(String(date));
      if (Number.isNaN(d.getTime())) return "";
      if (fmt === "iso") return d.toISOString();
      return d.toISOString().slice(0, 10);
    });
    this.hb.registerHelper("eq", (a: unknown, b: unknown) => a === b);
  }

  static async load(templateDir: string): Promise<TemplateEngine> {
    const engine = new TemplateEngine();

    const readDirSafe = async (dir: string) => {
      try {
        return (await fs.readdir(dir)).filter((f) => f.endsWith(".hbs"));
      } catch {
        return [];
      }
    };

    const partialsDir = path.join(templateDir, "partials");
    for (const file of await readDirSafe(partialsDir)) {
      const name = path.basename(file, ".hbs");
      engine.hb.registerPartial(name, await fs.readFile(path.join(partialsDir, file), "utf8"));
    }

    const layoutsDir = path.join(templateDir, "layouts");
    for (const file of await readDirSafe(layoutsDir)) {
      const name = path.basename(file, ".hbs");
      engine.layouts.set(name, engine.hb.compile(await fs.readFile(path.join(layoutsDir, file), "utf8")));
    }

    for (const file of await readDirSafe(templateDir)) {
      const name = path.basename(file, ".hbs");
      engine.pages.set(name, engine.hb.compile(await fs.readFile(path.join(templateDir, file), "utf8")));
    }

    return engine;
  }

  hasLayout(name: string): boolean {
    return this.layouts.has(name);
  }

  hasPage(name: string): boolean {
    return this.pages.has(name);
  }

  /** Render a layout by name; `content` is available as {{{content}}}. Falls back to "default". */
  renderLayout(name: string, context: Record<string, unknown>): string {
    const layout = this.layouts.get(name) ?? this.layouts.get("default");
    if (!layout) throw new Error(`No layout "${name}" and no "default" layout found`);
    return layout(context);
  }

  /** Render a top-level page template (index.hbs, tag.hbs). */
  renderPage(name: string, context: Record<string, unknown>): string {
    const page = this.pages.get(name);
    if (!page) throw new Error(`No page template "${name}.hbs" found in template directory`);
    return page(context);
  }
}
