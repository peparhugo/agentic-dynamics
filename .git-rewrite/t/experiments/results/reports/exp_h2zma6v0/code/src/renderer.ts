import fs from "node:fs/promises";
import path from "node:path";
import Handlebars from "handlebars";
import type { TemplateContext } from "./types.js";

export async function loadTemplates(templateDir: string): Promise<{
  layoutTemplate: Handlebars.TemplateDelegate<TemplateContext>;
  pageTemplate: Handlebars.TemplateDelegate<TemplateContext>;
  tagTemplate: Handlebars.TemplateDelegate<TemplateContext> | null;
  partials: Map<string, Handlebars.TemplateDelegate>;
}> {
  // Register a safeMarkdown (raw HTML) helper
  Handlebars.registerHelper("safeMarkdown", function (content: string) {
    return new Handlebars.SafeString(content);
  });

  // Load partials
  const partialsDir = path.join(templateDir, "partials");
  const partials = new Map<string, Handlebars.TemplateDelegate>();
  try {
    const entries = await fs.readdir(partialsDir);
    const hbsFiles = entries.filter((f) => f.endsWith(".hbs") || f.endsWith(".handlebars"));
    await Promise.all(
      hbsFiles.map(async (file) => {
        const content = await fs.readFile(path.join(partialsDir, file), "utf-8");
        const name = path.parse(file).name;
        partials.set(name, Handlebars.compile(content));
        Handlebars.registerPartial(name, content);
      })
    );
  } catch {
    // no partials dir — ok
  }

  // Load layout
  let layoutContent: string;
  try {
    layoutContent = await fs.readFile(path.join(templateDir, "layout.hbs"), "utf-8");
  } catch {
    layoutContent = await fs.readFile(path.join(templateDir, "layout.handlebars"), "utf-8");
  }
  const layoutTemplate = Handlebars.compile<TemplateContext>(layoutContent);

  // Load page
  let pageContent: string;
  try {
    pageContent = await fs.readFile(path.join(templateDir, "page.hbs"), "utf-8");
  } catch {
    pageContent = await fs.readFile(path.join(templateDir, "page.handlebars"), "utf-8");
  }
  const pageTemplate = Handlebars.compile<TemplateContext>(pageContent);

  // Load tag page (optional)
  let tagTemplate: Handlebars.TemplateDelegate<TemplateContext> | null = null;
  try {
    let tagContent: string;
    try {
      tagContent = await fs.readFile(path.join(templateDir, "tag.hbs"), "utf-8");
    } catch {
      tagContent = await fs.readFile(path.join(templateDir, "tag.handlebars"), "utf-8");
    }
    tagTemplate = Handlebars.compile<TemplateContext>(tagContent);
  } catch {
    // optional
  }

  return { layoutTemplate, pageTemplate, tagTemplate, partials };
}

export function renderPage(
  pageTemplate: Handlebars.TemplateDelegate<TemplateContext>,
  layoutTemplate: Handlebars.TemplateDelegate<TemplateContext>,
  context: TemplateContext
): string {
  const pageHtml = pageTemplate(context);
  const fullHtml = layoutTemplate({ ...context, page: { ...context.page, content: pageHtml } as TemplateContext["page"] });
  return fullHtml;
}

export function renderTagPage(
  tagTemplate: Handlebars.TemplateDelegate<TemplateContext>,
  layoutTemplate: Handlebars.TemplateDelegate<TemplateContext>,
  context: TemplateContext
): string {
  const pageHtml = tagTemplate(context);
  return layoutTemplate({ ...context, page: { ...context.page, content: pageHtml } as TemplateContext["page"] });
}
