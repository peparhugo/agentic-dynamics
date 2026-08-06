import fs from "fs";
import path from "path";
import Handlebars from "handlebars";
import { Page, BuildContext } from "./types";

export function loadTemplates(
  templatesDir: string
): Map<string, Handlebars.TemplateDelegate> {
  Handlebars.registerHelper("formatDate", function (date: string) {
    if (!date) return "";
    const d = new Date(date);
    return d.toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  });

  Handlebars.registerHelper("tagSlug", function (tag: string) {
    return tag.toLowerCase().replace(/\s+/g, "-");
  });

  const partialNames = new Set<string>();
  const layoutNames = new Set<string>();

  function discover(dir: string, prefix: string, isPartial: boolean) {
    if (!fs.existsSync(dir)) return;
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        discover(fullPath, prefix + entry.name + "/", isPartial);
      } else if (entry.name.endsWith(".hbs")) {
        const templateName = prefix + entry.name.slice(0, -4);
        const content = fs.readFileSync(fullPath, "utf-8");
        if (isPartial) {
          partialNames.add(templateName);
          Handlebars.registerPartial(templateName, content);
        } else {
          layoutNames.add(templateName);
          if (templateName !== "partial") {
            Handlebars.registerPartial(templateName, content);
          }
        }
      }
    }
  }

  const partialsDir = path.join(templatesDir, "partials");
  discover(partialsDir, "", true);

  discover(templatesDir, "", false);

  const templates = new Map<string, Handlebars.TemplateDelegate>();
  function compile(dir: string, prefix: string) {
    if (!fs.existsSync(dir)) return;
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (entry.name !== "partials") {
          compile(fullPath, prefix + entry.name + "/");
        }
      } else if (entry.name.endsWith(".hbs")) {
        const templateName = prefix + entry.name.slice(0, -4);
        if (!partialNames.has(templateName)) {
          const content = fs.readFileSync(fullPath, "utf-8");
          templates.set(templateName, Handlebars.compile(content));
        }
      }
    }
  }
  compile(templatesDir, "");

  return templates;
}

export function renderPage(
  template: Handlebars.TemplateDelegate,
  page: Page,
  ctx: BuildContext
): string {
  const allPages = ctx.pages.filter(
    (p) => !p.frontmatter.draft || p.slug === page.slug
  );
  const navPages = allPages.slice(0, 10);
  return template({
    page,
    title: page.frontmatter.title,
    date: page.frontmatter.date,
    tags: page.frontmatter.tags,
    content: page.html,
    siteTitle: ctx.siteTitle,
    siteUrl: ctx.siteUrl,
    siteDescription: ctx.siteDescription,
    pages: navPages,
    allTags: Array.from(ctx.tags.keys()).sort(),
    tagIndex: (tag: string) => {
      const pages = ctx.tags.get(tag) || [];
      return pages.filter((p) => !p.frontmatter.draft);
    },
  });
}

export function renderTagPage(
  template: Handlebars.TemplateDelegate,
  tag: string,
  ctx: BuildContext
): string {
  const tagPages = (ctx.tags.get(tag) || []).filter(
    (p) => !p.frontmatter.draft
  );
  const allPages = ctx.pages.filter((p) => !p.frontmatter.draft);
  return template({
    tag,
    pages: tagPages,
    siteTitle: ctx.siteTitle,
    siteUrl: ctx.siteUrl,
    siteDescription: ctx.siteDescription,
    allTags: Array.from(ctx.tags.keys()).sort(),
    title: `Posts tagged "${tag}"`,
    allPages,
  });
}

export function renderIndexPage(
  template: Handlebars.TemplateDelegate,
  ctx: BuildContext
): string {
  const publishedPages = ctx.pages.filter((p) => !p.frontmatter.draft);
  return template({
    pages: publishedPages,
    siteTitle: ctx.siteTitle,
    siteUrl: ctx.siteUrl,
    siteDescription: ctx.siteDescription,
    allTags: Array.from(ctx.tags.keys()).sort(),
    title: ctx.siteTitle,
  });
}
