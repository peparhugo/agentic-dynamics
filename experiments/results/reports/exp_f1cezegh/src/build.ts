import * as fs from "fs";
import * as path from "path";
import { Page, SiteConfig } from "./types";
import { parseFrontmatter } from "./frontmatter";
import { markdownToHtml } from "./highlight";
import { TemplateEngine } from "./render";
import { generateRSS } from "./rss";
import { generateTagIndexes, generateTagPageData } from "./tags";

export async function build(config: SiteConfig): Promise<void> {
  const pages = discoverPages(config.sourceDir);
  const engine = new TemplateEngine(config.templateDir);

  fs.rmSync(config.outputDir, { recursive: true, force: true });
  fs.mkdirSync(config.outputDir, { recursive: true });

  const published = pages.filter((p) => !p.meta.draft);

  for (const page of published) {
    renderPage(page, pages, published, engine, config);
  }

  renderIndex(published, engine, config);

  const tagIndexes = generateTagIndexes(pages);
  for (const [tag, tagPages] of tagIndexes.entries()) {
    renderTagPage(tag, tagPages, engine, config);
  }

  const rssXml = generateRSS(published, config);
  fs.writeFileSync(path.join(config.outputDir, "rss.xml"), rssXml);
}

function discoverPages(sourceDir: string): Page[] {
  const pages: Page[] = [];

  function walk(dir: string) {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(fullPath);
      } else if (entry.name.endsWith(".md")) {
        const raw = fs.readFileSync(fullPath, "utf-8");
        const { meta, content } = parseFrontmatter(raw);
        const relPath = path.relative(sourceDir, fullPath);
        const url = "/" + relPath.replace(/\.md$/, ".html");

        pages.push({ path: fullPath, url, meta, content, raw });
      }
    }
  }

  walk(sourceDir);
  return pages;
}

function renderPage(
  page: Page,
  allPages: Page[],
  published: Page[],
  engine: TemplateEngine,
  config: SiteConfig
): void {
  const html = markdownToHtml(page.content);
  const templateData = {
    ...page.meta,
    title: page.meta.title,
    date: page.meta.date,
    tags: page.meta.tags,
    body: html,
    content: html,
    page,
    pages: published.map(pickPageData),
    siteTitle: config.siteTitle,
    siteUrl: config.siteUrl,
    siteDescription: config.siteDescription,
  };

  let result: string;
  if (engine.hasTemplate("post")) {
    result = engine.render("post", templateData);
  } else {
    result = engine.renderString(
      `<html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>`,
      templateData
    );
  }

  const outPath = path.join(
    config.outputDir,
    page.url.replace(/^\//, "")
  );
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, result);
}

function renderIndex(published: Page[], engine: TemplateEngine, config: SiteConfig): void {
  const data = {
    title: config.siteTitle,
    pages: published.map(pickPageData),
    siteTitle: config.siteTitle,
    siteUrl: config.siteUrl,
    siteDescription: config.siteDescription,
  };

  let result: string;
  if (engine.hasTemplate("index")) {
    result = engine.render("index", data);
  } else {
    const items = published
      .map((p) => `<li><a href="${p.url}">${p.meta.title}</a></li>`)
      .join("");
    result = `<html><head><title>${config.siteTitle}</title></head><body><h1>${config.siteTitle}</h1><ul>${items}</ul></body></html>`;
  }

  fs.writeFileSync(path.join(config.outputDir, "index.html"), result);
}

function renderTagPage(
  tag: string,
  tagPages: Page[],
  engine: TemplateEngine,
  config: SiteConfig
): void {
  const data = generateTagPageData(tag, tagPages, config.siteTitle);

  let result: string;
  if (engine.hasTemplate("tag")) {
    result = engine.render("tag", data);
  } else {
    const items = tagPages
      .map((p) => `<li><a href="${p.url}">${p.meta.title}</a></li>`)
      .join("");
    result = `<html><head><title>Tag: ${tag}</title></head><body><h1>Tag: ${tag}</h1><ul>${items}</ul></body></html>`;
  }

  const outDir = path.join(config.outputDir, "tags");
  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, `${tag}.html`), result);
}

function pickPageData(p: Page) {
  return {
    title: p.meta.title,
    url: p.url,
    date: p.meta.date,
    tags: p.meta.tags,
  };
}
