import Handlebars from "handlebars";
import { readFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join, dirname, basename } from "node:path";
import { glob } from "node:fs/promises";
import { marked } from "marked";
import type { Page, Site, SiteConfig, TagIndex } from "./types.js";
import { highlightCode } from "./highlight.js";

export function markdownToHtml(md: string): string {
  return marked.parse(md, { async: false }) as string;
}

export async function registerPartials(templateDir: string): Promise<void> {
  const partialsDir = join(templateDir, "partials");
  if (!existsSync(partialsDir)) return;
  const files = await Array.fromAsync(glob("**/*.hbs", { cwd: partialsDir }));
  for (const file of files) {
    const name = basename(file, ".hbs");
    const content = await readFile(join(partialsDir, file), "utf-8");
    Handlebars.registerPartial(name, content);
  }
}

export function registerHelpers(): void {
  Handlebars.registerHelper("highlight", (code: string, lang?: string) => {
    return new Handlebars.SafeString(highlightCode(code, lang));
  });

  Handlebars.registerHelper("formatDate", (date: string | Date) => {
    const d = typeof date === "string" ? new Date(date) : date;
    return d.toISOString().slice(0, 10);
  });

  Handlebars.registerHelper("eq", (a: unknown, b: unknown) => a === b);
}

export async function loadLayouts(templateDir: string): Promise<Map<string, Handlebars.TemplateDelegate>> {
  const layouts = new Map<string, Handlebars.TemplateDelegate>();
  const layoutsDir = join(templateDir, "layouts");
  if (!existsSync(layoutsDir)) return layouts;
  const files = await Array.fromAsync(glob("*.hbs", { cwd: layoutsDir }));
  for (const file of files) {
    const name = basename(file, ".hbs");
    const content = await readFile(join(layoutsDir, file), "utf-8");
    layouts.set(name, Handlebars.compile(content));
  }
  return layouts;
}

export async function loadTemplate(templateDir: string, name: string): Promise<Handlebars.TemplateDelegate> {
  const filePath = join(templateDir, `${name}.hbs`);
  const content = await readFile(filePath, "utf-8");
  return Handlebars.compile(content);
}

export interface RenderContext {
  page: Page;
  site: Site;
  content?: string;
  [key: string]: unknown;
}

export async function renderPage(
  page: Page,
  site: Site,
  layouts: Map<string, Handlebars.TemplateDelegate>,
  templateDir: string,
): Promise<string> {
  const layoutName = page.frontmatter.layout || "default";
  const layout = layouts.get(layoutName);
  const templateName = page.template || (page.isPost ? "post" : "page");
  let contentHtml = page.html;

  if (page.content && !page.html) {
    contentHtml = markdownToHtml(page.content);
  }

  const template = await loadTemplate(templateDir, templateName).catch(async () => {
    return Handlebars.compile("{{{content}}}");
  });

  const innerHtml = template({ ...page, site, content: new Handlebars.SafeString(contentHtml) });

  if (layout) {
    return layout({
      ...page,
      site,
      content: new Handlebars.SafeString(innerHtml),
      page,
    });
  }

  return innerHtml;
}

export function buildSiteContext(pages: Page[], posts: Page[], tags: TagIndex[], config: SiteConfig): Site {
  return {
    pages,
    posts,
    pages2: pages,
    tags,
    config,
  };
}
