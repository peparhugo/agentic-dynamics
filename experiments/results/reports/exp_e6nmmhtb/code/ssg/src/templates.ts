import Handlebars from "handlebars";
import { readFile } from "node:fs/promises";
import { join, dirname, basename } from "node:path";
import { glob } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import type { Page, BuildContext } from "./types.js";

export async function loadTemplates(templateDir: string): Promise<void> {
  Handlebars.registerHelper("formatDate", (date: string) => {
    if (!date) return "";
    const d = new Date(date);
    if (isNaN(d.getTime())) return date;
    return d.toISOString().split("T")[0];
  });

  Handlebars.registerHelper("eq", (a: unknown, b: unknown) => a === b);
  Handlebars.registerHelper("hasTag", (tags: string[], tag: string) =>
    Array.isArray(tags) ? tags.includes(tag) : false,
  );

  const pattern = join(templateDir, "**/*.hbs").replace(/\\/g, "/");
  const files: string[] = [];
  for await (const f of glob(pattern)) {
    files.push(f);
  }

  for (const file of files) {
    const content = await readFile(file, "utf-8");
    const relative = file.replace(templateDir, "").replace(/^[/\\]/, "");
    const name = relative.replace(/\.hbs$/, "").replace(/\\/g, "/");

    if (name.startsWith("partials/")) {
      const partialName = name.replace("partials/", "");
      Handlebars.registerPartial(partialName, content);
    } else {
      Handlebars.registerPartial(name, content);
    }

    Handlebars.compile(content);
  }

  Handlebars.registerHelper("tagList", function (context: BuildContext) {
    const tags = [...context.tags.keys()].sort();
    let html = '<ul class="tag-list">';
    for (const tag of tags) {
      const count = context.tags.get(tag)!.length;
      html += `<li><a href="/tags/${tag}/">${tag}</a> (${count})</li>`;
    }
    html += "</ul>";
    return new Handlebars.SafeString(html);
  });

  Handlebars.registerHelper("tagCloud", function (context: BuildContext) {
    const entries = [...context.tags.entries()].sort((a, b) => a[0].localeCompare(b[0]));
    const max = Math.max(...entries.map(([, pages]) => pages.length), 1);
    let html = '<ul class="tag-cloud">';
    for (const [tag, pages] of entries) {
      const size = 80 + Math.round((pages.length / max) * 120);
      html += `<li style="font-size:${size}%"><a href="/tags/${tag}/">${tag}</a></li>`;
    }
    html += "</ul>";
    return new Handlebars.SafeString(html);
  });

  Handlebars.registerHelper("rssDate", (date: string) => {
    if (!date) return "";
    return date;
  });
}

function templateFor(name: string): HandlebarsTemplateDelegate | undefined {
  try {
    return Handlebars.compile(`{{> ${name}}}`);
  } catch {
    return undefined;
  }
}

export function renderPage(page: Page, context: BuildContext): string {
  const tplName = page.isPost ? "post" : (page.path === "posts/index.md" ? "index" : undefined);
  let tpl = tplName ? templateFor(tplName) : undefined;

  if (!tpl) {
    tpl = templateFor("default");
  }
  if (!tpl) {
    tpl = Handlebars.compile("{{{html}}}");
  }

  const layoutTpl = templateFor("layout");

  const innerHtml = tpl({ page, context });

  if (layoutTpl) {
    return layoutTpl({ page, context, body: new Handlebars.SafeString(innerHtml) });
  }

  return innerHtml;
}

export function renderString(template: string, data: Record<string, unknown>): string {
  const compiled = Handlebars.compile(template);
  return compiled(data);
}
