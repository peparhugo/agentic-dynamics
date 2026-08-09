import Handlebars from "handlebars";
import fs from "node:fs";
import path from "node:path";

export interface TemplateEngine {
  /** Render a named template (e.g. "post") with a context, wrapped in its layout. */
  render(name: string, context: Record<string, unknown>, layoutName?: string): string;
  hasTemplate(name: string): boolean;
}

const FALLBACK_LAYOUT = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{title}}</title>
</head>
<body>
{{{body}}}
</body>
</html>`;

const FALLBACK_PAGE = `<article><h1>{{page.frontmatter.title}}</h1>{{{page.html}}}</article>`;

const FALLBACK_TAG = `<h1>Tag: {{tag}}</h1>
<ul>
{{#each pages}}<li><a href="{{url}}">{{frontmatter.title}}</a></li>
{{/each}}
</ul>`;

const FALLBACK_INDEX = `<h1>{{site.title}}</h1>
<ul>
{{#each pages}}<li><a href="{{url}}">{{frontmatter.title}}</a>{{#if frontmatter.date}} — {{formatDate frontmatter.date}}{{/if}}</li>
{{/each}}
</ul>`;

function registerHelpers(hbs: typeof Handlebars): void {
  hbs.registerHelper("formatDate", (date: unknown, fmt?: unknown) => {
    if (!(date instanceof Date) || isNaN(date.getTime())) return "";
    if (typeof fmt === "string" && fmt === "iso") return date.toISOString();
    return date.toISOString().slice(0, 10);
  });
  hbs.registerHelper("join", (arr: unknown, sep: unknown) =>
    Array.isArray(arr) ? arr.join(typeof sep === "string" ? sep : ", ") : ""
  );
  hbs.registerHelper("eq", (a: unknown, b: unknown) => a === b);
}

/**
 * Load a Handlebars template environment from a directory.
 *
 * Convention:
 *   templates/
 *     layouts/    -> layouts ({{{body}}} receives the rendered page); default.hbs used unless overridden
 *     partials/   -> registered as partials by file name (without extension)
 *     *.hbs       -> page templates (post.hbs, index.hbs, tag.hbs, ...)
 *
 * Missing templates fall back to minimal built-ins so a bare source dir still builds.
 */
export function createTemplateEngine(templateDir: string): TemplateEngine {
  const hbs = Handlebars.create();
  registerHelpers(hbs);

  const templates = new Map<string, Handlebars.TemplateDelegate>();
  const layouts = new Map<string, Handlebars.TemplateDelegate>();

  const readHbsFiles = (dir: string): Array<{ name: string; source: string }> => {
    if (!fs.existsSync(dir)) return [];
    return fs
      .readdirSync(dir)
      .filter((f) => /\.(hbs|handlebars|html)$/.test(f))
      .map((f) => ({
        name: f.replace(/\.(hbs|handlebars|html)$/, ""),
        source: fs.readFileSync(path.join(dir, f), "utf8"),
      }));
  };

  for (const { name, source } of readHbsFiles(path.join(templateDir, "partials"))) {
    hbs.registerPartial(name, source);
  }
  for (const { name, source } of readHbsFiles(path.join(templateDir, "layouts"))) {
    layouts.set(name, hbs.compile(source));
  }
  for (const { name, source } of readHbsFiles(templateDir)) {
    templates.set(name, hbs.compile(source));
  }

  if (!layouts.has("default")) layouts.set("default", hbs.compile(FALLBACK_LAYOUT));
  if (!templates.has("post")) templates.set("post", hbs.compile(FALLBACK_PAGE));
  if (!templates.has("page")) templates.set("page", hbs.compile(FALLBACK_PAGE));
  if (!templates.has("tag")) templates.set("tag", hbs.compile(FALLBACK_TAG));
  if (!templates.has("index")) templates.set("index", hbs.compile(FALLBACK_INDEX));

  return {
    hasTemplate: (name) => templates.has(name),
    render(name, context, layoutName = "default") {
      const template = templates.get(name);
      if (!template) throw new Error(`Unknown template: ${name}`);
      const body = template(context);
      const layout = layouts.get(layoutName) ?? layouts.get("default")!;
      return layout({ ...context, body });
    },
  };
}
