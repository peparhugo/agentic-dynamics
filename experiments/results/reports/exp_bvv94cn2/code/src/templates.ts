import Handlebars from "handlebars";
import { readFile, readdir } from "node:fs/promises";
import { join, extname, relative, basename } from "node:path";

export interface TemplateEngine {
  render(template: string, data: Record<string, unknown>): string;
  renderPage(
    pageTemplate: string,
    data: Record<string, unknown>,
    layout?: string
  ): string;
}

let handlebars: typeof Handlebars;

export async function createEngine(templateDir: string): Promise<TemplateEngine> {
  const instance = Handlebars.create();
  handlebars = instance;

  // Load partials from partials/ subdirectory
  const partialsDir = join(templateDir, "partials");
  try {
    const partialFiles = await readdir(partialsDir, { withFileTypes: true });
    for (const entry of partialFiles) {
      if (entry.isFile() && extname(entry.name) === ".hbs") {
        const name = basename(entry.name, ".hbs");
        const content = await readFile(join(partialsDir, entry.name), "utf-8");
        instance.registerPartial(name, content);
      }
    }
  } catch {
    // No partials directory — that's fine
  }

  // Load templates from templateDir
  const templates = new Map<string, string>();
  try {
    const templateFiles = await readdir(templateDir, { withFileTypes: true });
    for (const entry of templateFiles) {
      if (entry.isFile() && extname(entry.name) === ".hbs" && entry.name !== "layout.hbs") {
        const name = basename(entry.name, ".hbs");
        const content = await readFile(join(templateDir, entry.name), "utf-8");
        templates.set(name, instance.compile(content)({}));
        instance.registerPartial(name, content);
      }
    }
  } catch {
    // No templates — that's fine
  }

  // Load layout if present
  let layoutSource = "";
  try {
    layoutSource = await readFile(join(templateDir, "layout.hbs"), "utf-8");
  } catch {
    // No layout
  }

  return {
    render(template: string, data: Record<string, unknown>): string {
      const compiled = instance.compile(template, { noEscape: true });
      return compiled(data);
    },

    renderPage(
      pageTemplate: string,
      data: Record<string, unknown>,
      layout?: string
    ): string {
      const compiledPage = instance.compile(pageTemplate);
      const body = compiledPage(data);

      const layoutTemplate = layout || layoutSource;
      if (!layoutTemplate) return body;

      const compiledLayout = instance.compile(layoutTemplate);
      return compiledLayout({ ...data, body: new instance.SafeString(body) });
    },
  };
}

// For tests — don't need templateDir
export function createTestEngine(
  partials?: Record<string, string>,
  layout?: string
): TemplateEngine {
  const instance = Handlebars.create();
  handlebars = instance;

  if (partials) {
    for (const [name, content] of Object.entries(partials)) {
      instance.registerPartial(name, content);
    }
  }

  return {
    render(template: string, data: Record<string, unknown>): string {
      const compiled = instance.compile(template, { noEscape: true });
      return compiled(data);
    },

    renderPage(
      pageTemplate: string,
      data: Record<string, unknown>,
      pageLayout?: string
    ): string {
      const compiledPage = instance.compile(pageTemplate);
      const body = compiledPage(data);

      const effectiveLayout = pageLayout || layout;
      if (!effectiveLayout) return body;

      const compiledLayout = instance.compile(effectiveLayout);
      return compiledLayout({ ...data, body: new instance.SafeString(body) });
    },
  };
}
