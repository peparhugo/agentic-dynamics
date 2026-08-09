import Handlebars from "handlebars";
import fs from "node:fs/promises";
import path from "node:path";
import type { BuildContext } from "./types.js";

export async function generateTagPages(
  ctx: BuildContext,
  templatesDir: string,
): Promise<Map<string, string>> {
  const results = new Map<string, string>();
  const tagTemplatePath = path.join(templatesDir, "tag.hbs");
  let templateSrc: string;
  try {
    templateSrc = await fs.readFile(tagTemplatePath, "utf-8");
  } catch {
    templateSrc = defaultTagTemplate();
  }

  const template = Handlebars.compile(templateSrc);

  for (const [tag, pages] of ctx.tagMap) {
    const html = template({
      site: { title: ctx.siteTitle },
      tag,
      pages: pages.map((p) => ({
        title: p.frontmatter.title,
        url: p.url,
        date: p.frontmatter.date,
        tags: p.tags,
      })),
    });
    results.set(tag, html);
  }

  return results;
}

function defaultTagTemplate(): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{{site.title}} - Tag: {{tag}}</title>
</head>
<body>
  <h1>Tag: {{tag}}</h1>
  <ul>
  {{#each pages}}
    <li>
      <a href="{{url}}">{{title}}</a>
      {{#if date}}<time>{{date}}</time>{{/if}}
    </li>
  {{/each}}
  </ul>
</body>
</html>`;
}
