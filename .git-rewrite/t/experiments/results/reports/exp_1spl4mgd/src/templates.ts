import Handlebars from "handlebars";
import fs from "node:fs/promises";
import path from "node:path";

const FALLBACK_LAYOUT = `<!doctype html>
<html>
<head><meta charset="utf-8"><title>{{page.title}} — {{site.title}}</title></head>
<body><main>{{{content}}}</main></body>
</html>`;

async function readDirIfExists(dir: string): Promise<string[]> {
  try {
    return await fs.readdir(dir);
  } catch {
    return [];
  }
}

/**
 * Handlebars-backed template engine.
 *
 * Directory layout:
 *   templates/
 *     layouts/   *.hbs   — page layouts, receive {{{content}}}, page, site, url
 *     partials/  *.hbs   — registered as partials by file name (no extension)
 */
export class TemplateEngine {
  private readonly hbs: typeof Handlebars;
  private readonly layouts = new Map<string, Handlebars.TemplateDelegate>();

  private constructor() {
    this.hbs = Handlebars.create();
    this.registerHelpers();
  }

  static async fromDir(templateDir: string): Promise<TemplateEngine> {
    const engine = new TemplateEngine();
    await engine.loadPartials(path.join(templateDir, "partials"));
    await engine.loadLayouts(path.join(templateDir, "layouts"));
    return engine;
  }

  /** In-memory construction, mainly for tests. */
  static fromSources(sources: {
    layouts?: Record<string, string>;
    partials?: Record<string, string>;
  }): TemplateEngine {
    const engine = new TemplateEngine();
    for (const [name, src] of Object.entries(sources.partials ?? {})) {
      engine.hbs.registerPartial(name, src);
    }
    for (const [name, src] of Object.entries(sources.layouts ?? {})) {
      engine.layouts.set(name, engine.hbs.compile(src));
    }
    return engine;
  }

  private registerHelpers(): void {
    this.hbs.registerHelper("formatDate", (value: unknown, format?: unknown) => {
      if (!(value instanceof Date) || Number.isNaN(value.getTime())) return "";
      if (format === "human") {
        return value.toLocaleDateString("en-US", {
          year: "numeric",
          month: "long",
          day: "numeric",
          timeZone: "UTC",
        });
      }
      return value.toISOString().slice(0, 10);
    });
    this.hbs.registerHelper("eq", (a: unknown, b: unknown) => a === b);
    this.hbs.registerHelper("join", (list: unknown, sep: unknown) =>
      Array.isArray(list) ? list.join(typeof sep === "string" ? sep : ", ") : ""
    );
  }

  private async loadPartials(dir: string): Promise<void> {
    for (const file of await readDirIfExists(dir)) {
      if (!file.endsWith(".hbs")) continue;
      const src = await fs.readFile(path.join(dir, file), "utf8");
      this.hbs.registerPartial(path.basename(file, ".hbs"), src);
    }
  }

  private async loadLayouts(dir: string): Promise<void> {
    for (const file of await readDirIfExists(dir)) {
      if (!file.endsWith(".hbs")) continue;
      const src = await fs.readFile(path.join(dir, file), "utf8");
      this.layouts.set(path.basename(file, ".hbs"), this.hbs.compile(src));
    }
  }

  hasLayout(name: string): boolean {
    return this.layouts.has(name);
  }

  /**
   * Render `context` with the named layout. Falls back to "default",
   * then to a built-in minimal layout.
   */
  render(layoutName: string, context: Record<string, unknown>): string {
    const layout =
      this.layouts.get(layoutName) ??
      this.layouts.get("default") ??
      this.hbs.compile(FALLBACK_LAYOUT);
    return layout(context);
  }
}
