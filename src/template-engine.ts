import Handlebars from "handlebars";
import { promises as fs } from "fs";
import path from "path";
import { Frontmatter, PageData } from "./types";

interface CompiledTemplates {
  templates: Map<string, HandlebarsTemplateDelegate>;
  layouts: Map<string, HandlebarsTemplateDelegate>;
}

export interface TemplateEngine {
  renderPage(
    frontmatter: Frontmatter,
    content: string,
    template?: string,
    layout?: string
  ): string;
  renderIndex(pages: PageData[]): string;
}

async function loadTemplateFiles(
  dir: string
): Promise<Map<string, HandlebarsTemplateDelegate>> {
  const map = new Map<string, HandlebarsTemplateDelegate>();
  let entries: { name: string; isDirectory: boolean }[];
  try {
    const dirents = await fs.readdir(dir, { withFileTypes: true });
    entries = dirents.map((e) => ({ name: e.name, isDirectory: e.isDirectory() }));
  } catch {
    return map;
  }

  for (const entry of entries) {
    if (entry.isDirectory) continue;
    const ext = path.extname(entry.name);
    if (ext !== ".hbs" && ext !== ".handlebars") continue;
    const name = path.basename(entry.name, ext);
    const templatePath = path.join(dir, entry.name);
    const source = await fs.readFile(templatePath, "utf-8");
    map.set(name, Handlebars.compile(source));
  }

  return map;
}

async function loadPartials(
  dir: string
): Promise<void> {
  let entries: { name: string; isDirectory: boolean }[];
  try {
    const dirents = await fs.readdir(dir, { withFileTypes: true });
    entries = dirents.map((e) => ({ name: e.name, isDirectory: e.isDirectory() }));
  } catch {
    return;
  }

  for (const entry of entries) {
    if (entry.isDirectory) continue;
    const ext = path.extname(entry.name);
    if (ext !== ".hbs" && ext !== ".handlebars") continue;
    const name = path.basename(entry.name, ext);
    const templatePath = path.join(dir, entry.name);
    const source = await fs.readFile(templatePath, "utf-8");
    Handlebars.registerPartial(name, source);
  }
}

export async function createTemplateEngine(
  templatesDir: string
): Promise<TemplateEngine | null> {
  const absDir = path.resolve(templatesDir);

  try {
    await fs.access(absDir);
  } catch {
    return null;
  }

  const partialsDir = path.join(absDir, "partials");
  await loadPartials(partialsDir);

  const layoutDir = path.join(absDir, "layouts");
  const [templates, layouts] = await Promise.all([
    loadTemplateFiles(absDir),
    loadTemplateFiles(layoutDir),
  ]);

  if (templates.size === 0 && layouts.size === 0) {
    return null;
  }

  const compiled: CompiledTemplates = { templates, layouts };

  return {
    renderPage(
      frontmatter: Frontmatter,
      content: string,
      template?: string,
      layout?: string
    ): string {
      const templateData: Record<string, unknown> = {
        ...frontmatter,
        content,
      };

      const pageLayout = layout || frontmatter.layout;
      const pageTemplate = template || frontmatter.template || "default";

      let rendered: string;

      const tpl =
        compiled.templates.get(pageTemplate) ||
        (pageTemplate === "default"
          ? compiled.templates.values().next().value
          : undefined);

      if (tpl) {
        rendered = tpl(templateData);
      } else {
        compiled.templates.values().next().value;
        const firstTpl = compiled.templates.values().next().value;
        if (firstTpl) {
          rendered = firstTpl(templateData);
        } else {
          return content;
        }
      }

      if (pageLayout) {
        const layoutTpl = compiled.layouts.get(pageLayout);
        if (layoutTpl) {
          rendered = layoutTpl({ ...templateData, body: rendered });
        }
      }

      return rendered;
    },

    renderIndex(pages: PageData[]): string {
      const indexTpl = compiled.templates.get("index");
      if (!indexTpl) {
        return "";
      }

      const items = pages.map((page) => ({
        href: page.path.replace(/\.md$/, ".html"),
        title: page.frontmatter.title || page.path,
        date: page.frontmatter.date || "",
        tags: page.frontmatter.tags || "",
      }));

      return indexTpl({ pages: items });
    },
  };
}
