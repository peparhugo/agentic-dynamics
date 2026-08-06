import Handlebars from "handlebars";
import fs from "node:fs/promises";
import path from "node:path";
import type { Page } from "./types.js";

export interface TemplateEngine {
  render(page: Page, content: string, context: Record<string, unknown>): string;
}

export async function createTemplateEngine(
  templatesDir: string,
): Promise<TemplateEngine> {
  await registerPartials(templatesDir);

  const layoutCache = new Map<string, HandlebarsTemplateDelegate>();

  async function getLayout(name: string): Promise<HandlebarsTemplateDelegate> {
    if (layoutCache.has(name)) return layoutCache.get(name)!;
    const layoutPath = path.join(templatesDir, "layouts", `${name}.hbs`);
    const src = await fs.readFile(layoutPath, "utf-8");
    const compiled = Handlebars.compile(src);
    layoutCache.set(name, compiled);
    return compiled;
  }

  return {
    render(page: Page, content: string, context: Record<string, unknown>) {
      const layoutName = page.frontmatter.layout ?? "default";
      return getLayout(layoutName).then((layout) =>
        layout({
          ...context,
          content,
          page: {
            title: page.frontmatter.title,
            date: page.frontmatter.date,
            tags: page.tags,
            url: page.url,
            ...page.frontmatter,
          },
        }),
      );
    },
  };
}

async function registerPartials(templatesDir: string): Promise<void> {
  const partialsDir = path.join(templatesDir, "partials");
  try {
    const entries = await fs.readdir(partialsDir, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.isFile() && entry.name.endsWith(".hbs")) {
        const name = entry.name.replace(/\.hbs$/, "");
        const src = await fs.readFile(path.join(partialsDir, entry.name), "utf-8");
        Handlebars.registerPartial(name, src);
      }
    }
  } catch {
    // partials directory may not exist, that's ok
  }
}

Handlebars.registerHelper("formatDate", (date: string | undefined) => {
  if (!date) return "";
  const d = new Date(date);
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
});

Handlebars.registerHelper("rfc822Date", (date: string | undefined) => {
  if (!date) return "";
  return new Date(date).toUTCString();
});

Handlebars.registerHelper("eq", (a: unknown, b: unknown) => a === b);
