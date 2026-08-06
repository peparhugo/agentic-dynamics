import fs from "node:fs/promises";
import path from "node:path";
import Handlebars from "handlebars";
import type { Page, TagIndex, SiteConfig } from "./types.js";

async function loadTemplates(templateDir: string): Promise<{
  templates: Map<string, HandlebarsTemplateDelegate>;
  partials: Map<string, string>;
}> {
  const templates = new Map<string, HandlebarsTemplateDelegate>();
  const partials = new Map<string, string>();

  const entries = await fs.readdir(templateDir, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isFile() || !entry.name.endsWith(".hbs")) {
      continue;
    }
    const filePath = path.join(templateDir, entry.name);
    const source = await fs.readFile(filePath, "utf-8");
    const name = path.parse(entry.name).name;

    if (name.startsWith("_")) {
      partials.set(name.slice(1), source);
    } else {
      templates.set(name, Handlebars.compile(source));
    }
  }

  return { templates, partials };
}

export async function compileTemplates(templateDir: string): Promise<{
  templates: Map<string, HandlebarsTemplateDelegate>;
  partials: Map<string, string>;
}> {
  const result = await loadTemplates(templateDir);

  for (const [name, source] of result.partials) {
    Handlebars.registerPartial(name, source);
  }

  return result;
}

export function renderPage(
  page: Page,
  template: HandlebarsTemplateDelegate,
  allPages: Page[],
  config: SiteConfig,
): string {
  const sorted = [...allPages]
    .filter((p) => !p.isDraft)
    .sort((a, b) => {
      const da = a.frontmatter.date ?? "";
      const db = b.frontmatter.date ?? "";
      return db.localeCompare(da);
    });

  return template({
    page,
    pages: sorted,
    config,
    title: page.frontmatter.title,
    date: page.frontmatter.date ?? null,
    tags: page.frontmatter.tags ?? [],
    content: page.html,
  });
}

export function renderTagPage(
  tagIndex: TagIndex,
  template: HandlebarsTemplateDelegate,
  config: SiteConfig,
): string {
  const sorted = [...tagIndex.pages].sort((a, b) => {
    const da = a.frontmatter.date ?? "";
    const db = b.frontmatter.date ?? "";
    return db.localeCompare(da);
  });

  return template({
    tag: tagIndex.tag,
    pages: sorted,
    config,
    title: `Tag: ${tagIndex.tag}`,
  });
}

export function renderIndex(
  pages: Page[],
  template: HandlebarsTemplateDelegate,
  config: SiteConfig,
): string {
  const sorted = [...pages]
    .filter((p) => !p.isDraft)
    .sort((a, b) => {
      const da = a.frontmatter.date ?? "";
      const db = b.frontmatter.date ?? "";
      return db.localeCompare(da);
    });

  return template({
    pages: sorted,
    config,
    title: config.title,
  });
}
