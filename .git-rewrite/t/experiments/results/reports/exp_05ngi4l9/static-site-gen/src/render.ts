import fs from "node:fs/promises";
import path from "node:path";
import Handlebars from "handlebars";
import { formatDate } from "./frontmatter.js";

export interface Templates {
  layout: Handlebars.TemplateDelegate | null;
  post: Handlebars.TemplateDelegate;
  index: Handlebars.TemplateDelegate;
  tag: Handlebars.TemplateDelegate;
  rss: Handlebars.TemplateDelegate | null;
  reloadScript: string;
}

export async function loadTemplates(templateDir: string): Promise<Templates> {
  const partialsDir = path.join(templateDir, "partials");
  try {
    const partialFiles = await fs.readdir(partialsDir);
    for (const file of partialFiles) {
      if (!file.endsWith(".hbs")) continue;
      const name = path.basename(file, ".hbs");
      const src = await fs.readFile(path.join(partialsDir, file), "utf-8");
      Handlebars.registerPartial(name, src);
    }
  } catch {
    // No partials directory
  }

  registerHelpers();

  const readTemplate = async (name: string): Promise<Handlebars.TemplateDelegate> => {
    const src = await fs.readFile(path.join(templateDir, `${name}.hbs`), "utf-8");
    return Handlebars.compile(src);
  };

  const optTemplate = async (name: string): Promise<Handlebars.TemplateDelegate | null> => {
    try {
      return await readTemplate(name);
    } catch {
      return null;
    }
  };

  const [post, index, tag, layout, rss] = await Promise.all([
    readTemplate("post"),
    readTemplate("index"),
    readTemplate("tag"),
    optTemplate("layout"),
    optTemplate("rss"),
  ]);

  const reloadScript = await fs
    .readFile(path.join(templateDir, "reload.hbs"), "utf-8")
    .catch(() => "");

  return { layout, post, index, tag, rss, reloadScript };
}

function registerHelpers(): void {
  Handlebars.registerHelper("formatDate", (date: unknown) => {
    if (typeof date === "string" || date instanceof Date) {
      return formatDate(date);
    }
    return "";
  });

  Handlebars.registerHelper("tagList", (tags: string[] | undefined) => {
    return (tags ?? []).join(", ");
  });

  Handlebars.registerHelper("rssDate", (date: unknown) => {
    if (typeof date === "string" || date instanceof Date) {
      return new Date(date).toUTCString();
    }
    return "";
  });
}

export function applyLayout(
  templates: Templates,
  body: string,
  context: Record<string, unknown>
): string {
  const scriptTag = templates.reloadScript ? `<script>${templates.reloadScript}</script>` : "";

  if (templates.layout) {
    return templates.layout(
      { ...context, body, reloadScript: scriptTag },
      { allowProtoPropertiesByDefault: true }
    );
  }

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${context.title ?? ""}</title>
</head>
<body>
${body}
${scriptTag}
</body>
</html>`;
}
