import { readFile, readdir } from "node:fs/promises";
import { join, extname } from "node:path";
import { marked } from "marked";
import { markedHighlight } from "marked-highlight";
import hljs from "highlight.js";
import Handlebars from "handlebars";

marked.use(
  markedHighlight({
    langPrefix: "hljs language-",
    highlight(code: string, lang: string) {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(code, { language: lang }).value;
      }
      return code;
    },
  }),
);

interface TemplateEntry {
  name: string;
  fn: HandlebarsTemplateDelegate;
}

export interface LoadedTemplates {
  layout: HandlebarsTemplateDelegate | null;
  templates: Map<string, HandlebarsTemplateDelegate>;
  partials: Map<string, HandlebarsTemplateDelegate>;
}

async function compileDir(dir: string): Promise<TemplateEntry[]> {
  const entries: TemplateEntry[] = [];
  const files = await readdir(dir).catch(() => [] as string[]);
  for (const f of files) {
    const full = join(dir, f);
    if (!f.endsWith(".hbs") && !f.endsWith(".handlebars")) continue;
    const src = await readFile(full, "utf-8");
    entries.push({ name: f.replace(/\.(hbs|handlebars)$/, ""), fn: Handlebars.compile(src) });
  }
  return entries;
}

export async function loadTemplates(tmplDir: string): Promise<LoadedTemplates> {
  const [templates, partials] = await Promise.all([
    compileDir(tmplDir),
    compileDir(join(tmplDir, "partials")),
  ]);

  let layout: HandlebarsTemplateDelegate | null = null;
  const tmap = new Map<string, HandlebarsTemplateDelegate>();

  for (const t of templates) {
    if (t.name === "layout") {
      layout = t.fn;
    } else {
      tmap.set(t.name, t.fn);
    }
  }

  const pmap = new Map<string, HandlebarsTemplateDelegate>();
  for (const p of partials) {
    Handlebars.registerPartial(p.name, p.fn);
    pmap.set(p.name, p.fn);
  }

  return { layout, templates: tmap, partials: pmap };
}

export function renderMarkdown(md: string): string {
  return marked.parse(md, { async: false }) as string;
}

export function renderTemplate(
  templates: LoadedTemplates,
  templateName: string,
  data: Record<string, unknown>,
): string {
  const t = templates.templates.get(templateName);
  if (!t) throw new Error(`Template "${templateName}" not found`);
  const body = t(data);
  if (templates.layout) {
    return templates.layout({ ...data, body });
  }
  return body;
}
