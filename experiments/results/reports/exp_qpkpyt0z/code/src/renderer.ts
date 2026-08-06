import Handlebars from "handlebars";
import { readFile, readdir, access } from "node:fs/promises";
import { join, relative, dirname, extname } from "node:path";
import type { Page, TagInfo, SiteConfig } from "./types.js";

const templateCache = new Map<string, HandlebarsTemplateDelegate>();

export function registerPartial(name: string, source: string): void {
  Handlebars.registerPartial(name, source);
}

export function registerHelper(name: string, fn: Handlebars.HelperDelegate): void {
  Handlebars.registerHelper(name, fn);
}

export function compile(source: string): HandlebarsTemplateDelegate {
  return Handlebars.compile(source, { noEscape: true });
}

async function readTemplateFile(filePath: string): Promise<string> {
  const cached = templateCache.get(filePath);
  if (cached) return (cached as unknown as string);
  const content = await readFile(filePath, "utf-8");
  templateCache.set(filePath, content as unknown as HandlebarsTemplateDelegate);
  return content;
}

export async function loadPartials(partialsDir: string): Promise<void> {
  try {
    await access(partialsDir);
  } catch {
    return;
  }
  const entries = await readdir(partialsDir, { withFileTypes: true });
  await Promise.all(
    entries
      .filter((e) => e.isFile() && extname(e.name) === ".hbs")
      .map(async (entry) => {
        const name = basename(entry.name, ".hbs") as string;
        const source = await readTemplateFile(join(partialsDir, entry.name));
        registerPartial(name, source);
      })
  );
}

export async function loadTemplate(
  config: SiteConfig,
  name: string
): Promise<HandlebarsTemplateDelegate> {
  const filePath = join(config.templateDir, `${name}.hbs`);
  const cached = templateCache.get(filePath);
  if (cached) return cached;
  const source = await readTemplateFile(filePath);
  const fn = compile(source);
  templateCache.set(filePath, fn);
  return fn;
}

export async function renderPage(
  config: SiteConfig,
  templateName: string,
  data: Record<string, unknown>
): Promise<string> {
  const template = await loadTemplate(config, templateName);
  return template(data);
}

export async function renderAllPages(
  pages: Page[],
  config: SiteConfig,
  tags: TagInfo[]
): Promise<Map<string, string>> {
  const output = new Map<string, string>();
  const publishable = pages.filter((p) => !p.isDraft);
  const sorted = [...publishable].sort(
    (a, b) =>
      new Date(b.frontmatter.date ?? 0).getTime() -
      new Date(a.frontmatter.date ?? 0).getTime()
  );

  const pageResults: Promise<[string, string]>[] = pages.map(async (page): Promise<[string, string]> => {
    const html = await renderPage(config, "post", {
      ...page.frontmatter,
      content: page.html,
      url: page.url,
      site: {
        title: config.siteTitle,
        url: config.siteUrl,
      },
      pages: publishable,
      tags,
    });
    return [page.url, html];
  });

  const indexPromise = (async (): Promise<[string, string]> => {
    const indexHtml = await renderPage(config, "index", {
      pages: sorted,
      site: { title: config.siteTitle, url: config.siteUrl },
      tags,
    });
    return ["/index.html", indexHtml];
  })();

  const tagPromises: Promise<[string, string]>[] = tags.map(async (tag): Promise<[string, string]> => {
    const html = await renderPage(config, "tag", {
      tag,
      pages: tag.pages,
      allTags: tags,
      site: { title: config.siteTitle, url: config.siteUrl },
    });
    return [`/tags/${tag.name}/index.html`, html];
  });

  const allResults = await Promise.all([...pageResults, indexPromise, ...tagPromises]);

  for (const [url, html] of allResults) {
    output.set(url, html);
  }

  return output;
}

export function basename(name: string, ext: string): string {
  const idx = name.lastIndexOf(ext);
  return idx >= 0 ? name.slice(0, idx) : name;
}
