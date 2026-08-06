import Handlebars from "handlebars";
import fs from "fs";
import path from "path";
import { Page, GeneratorOptions } from "./types";

/**
 * Configure Handlebars with templates, partials, and a layout convention.
 * Layout: if a template has {{body}}, child content is injected there.
 * Otherwise, child content replaces the template entirely.
 */
export function configureTemplateEngine(templateDir: string): Handlebars.TemplateDelegate<Record<string, unknown>> | null {
  // Register partials from templateDir/partials/
  const partialsDir = path.join(templateDir, "partials");
  if (fs.existsSync(partialsDir)) {
    for (const f of fs.readdirSync(partialsDir)) {
      const fp = path.join(partialsDir, f);
      if (f.endsWith(".hbs") || f.endsWith(".handlebars")) {
        const name = path.parse(f).name;
        Handlebars.registerPartial(name, fs.readFileSync(fp, "utf-8"));
      }
    }
  }

  // Look for a default layout: layout.hbs in the template root
  const layoutPath = path.join(templateDir, "layout.hbs");
  if (fs.existsSync(layoutPath)) {
    return Handlebars.compile(fs.readFileSync(layoutPath, "utf-8"));
  }
  return null;
}

export function renderPage(
  page: Page,
  pages: Page[],
  templateDir: string,
  layout: Handlebars.TemplateDelegate<Record<string, unknown>> | null,
  options: GeneratorOptions
): string {
  const { frontmatter, html: content } = page;

  // Resolve a page-specific template if present: frontmatter.template points to a .hbs file
  let pageTemplate: Handlebars.TemplateDelegate<Record<string, unknown>> | null = null;
  if (frontmatter.template && typeof frontmatter.template === "string") {
    const tplPath = path.join(templateDir, frontmatter.template);
    if (fs.existsSync(tplPath)) {
      pageTemplate = Handlebars.compile(fs.readFileSync(tplPath, "utf-8"));
    }
  }

  // Tags: collect pages with matching tags for tag-related helpers
  const tagMap = buildTagMap(pages.filter(p => !p.frontmatter.draft));
  const thisTags = frontmatter.tags || [];

  const ctx: Record<string, unknown> = {
    title: frontmatter.title || path.basename(page.sourcePath, ".md"),
    date: frontmatter.date || "",
    tags: thisTags,
    draft: !!frontmatter.draft,
    content,
    pages: pages
      .filter(p => !p.frontmatter.draft)
      .map(p => ({
        title: p.frontmatter.title || path.basename(p.sourcePath, ".md"),
        path: p.path,
        date: p.frontmatter.date || "",
        tags: p.frontmatter.tags || [],
      })),
    site: options.config,
    frontmatter,
    ...frontmatter,
  };

  let body: string;
  if (pageTemplate) {
    body = pageTemplate(ctx);
  } else {
    body = content;
  }

  if (layout) {
    return layout({ ...ctx, body });
  }
  return body;
}

export function buildTagMap(pages: Page[]): Map<string, Page[]> {
  const map = new Map<string, Page[]>();
  for (const p of pages) {
    for (const tag of p.frontmatter.tags || []) {
      if (!map.has(tag)) map.set(tag, []);
      map.get(tag)!.push(p);
    }
  }
  return map;
}

export function generateTagIndex(
  tag: string,
  taggedPages: Page[],
  layout: Handlebars.TemplateDelegate<Record<string, unknown>> | null,
  options: GeneratorOptions
): string {
  const ctx: Record<string, unknown> = {
    title: `Tag: ${tag}`,
    tag,
    pages: taggedPages.map(p => ({
      title: p.frontmatter.title || path.basename(p.sourcePath, ".md"),
      path: p.path,
      date: p.frontmatter.date || "",
      tags: p.frontmatter.tags || [],
    })),
    site: options.config,
  };
  const body = `<h1>Tag: ${tag}</h1><ul>${taggedPages
    .map(p => `<li><a href="${p.path}">${p.frontmatter.title || path.basename(p.sourcePath, ".md")}</a></li>`)
    .join("")}</ul>`;

  if (layout) {
    return layout({ ...ctx, body });
  }
  return `<!DOCTYPE html><html><head><title>${ctx.title}</title></head><body>${body}</body></html>`;
}
