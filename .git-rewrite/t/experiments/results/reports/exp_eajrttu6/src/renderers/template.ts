import fs from "fs";
import path from "path";
import Handlebars from "handlebars";
import type { Page, SiteConfig, TagIndexEntry } from "../types";

export class TemplateEngine {
  private partialsDir: string;
  private layoutDir: string;
  private compiledPartials: Map<string, HandlebarsTemplateDelegate> =
    new Map();
  private compiledLayouts: Map<string, HandlebarsTemplateDelegate> =
    new Map();

  constructor(templatesDir: string) {
    this.partialsDir = path.join(templatesDir, "partials");
    this.layoutDir = path.join(templatesDir, "layouts");
    this.registerPartials();
    this.registerHelpers();
  }

  private registerHelpers() {
    Handlebars.registerHelper("formatDate", (date: string) => {
      if (!date) return "";
      return new Date(date).toLocaleDateString("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric",
      });
    });

    Handlebars.registerHelper("isoDate", (date: string) => {
      if (!date) return "";
      return new Date(date).toISOString();
    });

    Handlebars.registerHelper("excerpt", (html: string, words: number) => {
      const text = html.replace(/<[^>]*>/g, "");
      const trimmed = text.split(/\s+/).slice(0, words).join(" ");
      return trimmed + (text.split(/\s+/).length > words ? "..." : "");
    });

    Handlebars.registerHelper("eq", (a: unknown, b: unknown) => a === b);
  }

  private registerPartials() {
    if (!fs.existsSync(this.partialsDir)) return;
    const files = fs.readdirSync(this.partialsDir);
    for (const file of files) {
      if (file.endsWith(".hbs") || file.endsWith(".html")) {
        const name = path.parse(file).name;
        const content = fs.readFileSync(
          path.join(this.partialsDir, file),
          "utf-8"
        );
        Handlebars.registerPartial(name, content);
      }
    }
  }

  private compileTemplate(templatePath: string): HandlebarsTemplateDelegate {
    const content = fs.readFileSync(templatePath, "utf-8");
    return Handlebars.compile(content);
  }

  private getLayout(layoutName: string | undefined): HandlebarsTemplateDelegate {
    const name = layoutName || "default";
    if (this.compiledLayouts.has(name)) {
      return this.compiledLayouts.get(name)!;
    }
    // Try layouts dir, then root
    const candidates = [
      path.join(this.layoutDir, `${name}.hbs`),
      path.join(this.layoutDir, `${name}.html`),
    ];
    for (const candidate of candidates) {
      if (fs.existsSync(candidate)) {
        const compiled = this.compileTemplate(candidate);
        this.compiledLayouts.set(name, compiled);
        return compiled;
      }
    }
    // Fallback: simple wrapper layout
    const fallback = Handlebars.compile("{{{body}}}");
    this.compiledLayouts.set(name, fallback);
    return fallback;
  }

  renderPage(
    page: Page,
    allPages: Page[],
    site: SiteConfig
  ): string {
    const layout = this.getLayout(page.frontmatter.layout);
    return layout({
      page,
      pages: allPages,
      site,
    });
  }

  renderIndex(
    pages: Page[],
    site: SiteConfig,
    templateName: string = "index"
  ): string {
    const candidates = [
      path.join(this.layoutDir, `${templateName}.hbs`),
      path.join(this.layoutDir, `${templateName}.html`),
    ];

    for (const candidate of candidates) {
      if (fs.existsSync(candidate)) {
        const compiled = this.compileTemplate(candidate);
        return compiled({ pages, site });
      }
    }

    // Default index template
    const defaultIndex = Handlebars.compile(`<!DOCTYPE html>
<html lang="{{site.language}}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{site.title}}</title>
</head>
<body>
  <h1>{{site.title}}</h1>
  {{#each pages}}
  <article>
    <h2><a href="/{{slug}}.html">{{frontmatter.title}}</a></h2>
    {{#if frontmatter.date}}<time>{{frontmatter.date}}</time>{{/if}}
    <div>{{{html}}}</div>
  </article>
  {{/each}}
</body>
</html>`);
    return defaultIndex({ pages, site });
  }

  renderTagPage(
    tagEntry: TagIndexEntry,
    site: SiteConfig
  ): string {
    const candidates = [
      path.join(this.layoutDir, "tag.hbs"),
      path.join(this.layoutDir, "tag.html"),
    ];

    for (const candidate of candidates) {
      if (fs.existsSync(candidate)) {
        const compiled = this.compileTemplate(candidate);
        return compiled({ tag: tagEntry.tag, pages: tagEntry.pages, site });
      }
    }

    const defaultTag = Handlebars.compile(`<!DOCTYPE html>
<html lang="{{site.language}}">
<head>
  <meta charset="UTF-8">
  <title>Tag: {{tag}} - {{site.title}}</title>
</head>
<body>
  <h1>Posts tagged "{{tag}}"</h1>
  {{#each pages}}
  <article>
    <h2><a href="/{{slug}}.html">{{frontmatter.title}}</a></h2>
    {{#if frontmatter.date}}<time>{{frontmatter.date}}</time>{{/if}}
  </article>
  {{/each}}
</body>
</html>`);
    return defaultTag({ tag: tagEntry.tag, pages: tagEntry.pages, site });
  }
}
