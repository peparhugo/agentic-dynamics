import Handlebars from "handlebars";
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join, extname } from "node:path";
import { Page, SiteConfig } from "./types.js";

export function loadTemplates(config: SiteConfig): {
  layouts: Map<string, Handlebars.TemplateDelegate>;
  renderPage: (page: Page, pages: Page[]) => string;
} {
  const layouts = new Map<string, Handlebars.TemplateDelegate>();

  registerPartials(config.templateDir);
  registerLayouts(config.templateDir, layouts);

  function renderPage(page: Page, pages: Page[]): string {
    const layoutName = page.frontmatter.layout ?? "default";
    const layout = layouts.get(layoutName);

    const templateData = {
      ...page.frontmatter,
      content: page.html,
      page,
      pages: pages.filter((p) => !p.frontmatter.draft),
      site: { title: config.siteTitle },
    };

    if (layout) {
      return layout(templateData);
    }

    return page.html;
  }

  return { layouts, renderPage };
}

function registerPartials(templateDir: string): void {
  const partialsDir = join(templateDir, "partials");
  if (!existsSync(partialsDir)) return;

  for (const file of readdirSync(partialsDir)) {
    if (!file.endsWith(".hbs") && !file.endsWith(".handlebars")) continue;
    const name = file.replace(/\.(hbs|handlebars)$/, "");
    const source = readFileSync(join(partialsDir, file), "utf-8");
    Handlebars.registerPartial(name, source);
  }
}

function registerLayouts(
  templateDir: string,
  layouts: Map<string, Handlebars.TemplateDelegate>
): void {
  if (!existsSync(templateDir)) return;

  for (const file of readdirSync(templateDir)) {
    const ext = extname(file);
    if (ext !== ".hbs" && ext !== ".handlebars") continue;
    const name = file.replace(/\.(hbs|handlebars)$/, "");
    const source = readFileSync(join(templateDir, file), "utf-8");
    layouts.set(name, Handlebars.compile(source));
  }
}
