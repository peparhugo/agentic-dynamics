import fs from "fs";
import path from "path";
import { loadPages } from "../parsers/markdown";
import { TemplateEngine } from "../renderers/template";
import { buildTagIndex } from "../generators/index";
import { buildRssFeed } from "../generators/rss";
import type { SiteConfig } from "../types";

export interface BuildOptions {
  sourceDir: string;
  outputDir: string;
  templatesDir: string;
  site: SiteConfig;
  verbose?: boolean;
}

export function build(options: BuildOptions): number {
  const { sourceDir, outputDir, templatesDir, site, verbose } = options;

  if (!fs.existsSync(sourceDir)) {
    console.error(`Source directory not found: ${sourceDir}`);
    return 1;
  }

  if (verbose) console.log(`Loading pages from ${sourceDir}...`);
  const { pages } = loadPages(sourceDir, outputDir);
  if (verbose) console.log(`Found ${pages.length} pages.`);

  const engine = new TemplateEngine(templatesDir);

  if (verbose) console.log(`Writing output to ${outputDir}...`);
  fs.rmSync(outputDir, { recursive: true, force: true });
  fs.mkdirSync(outputDir, { recursive: true });

  for (const page of pages) {
    const html = engine.renderPage(page, pages, site);
    fs.mkdirSync(path.dirname(page.outputPath), { recursive: true });
    fs.writeFileSync(page.outputPath, html, "utf-8");
    if (verbose) console.log(`  ${page.slug}.html`);
  }

  const indexHtml = engine.renderIndex(pages, site);
  fs.writeFileSync(path.join(outputDir, "index.html"), indexHtml, "utf-8");
  if (verbose) console.log("  index.html");

  const tagEntries = buildTagIndex(pages);
  const tagsDir = path.join(outputDir, "tags");
  fs.mkdirSync(tagsDir, { recursive: true });
  for (const entry of tagEntries) {
    const tagHtml = engine.renderTagPage(entry, site);
    const tagOutputPath = path.join(tagsDir, `${entry.tag}.html`);
    fs.writeFileSync(tagOutputPath, tagHtml, "utf-8");
    if (verbose) console.log(`  tags/${entry.tag}.html`);
  }

  const rssXml = buildRssFeed(pages, site);
  fs.writeFileSync(path.join(outputDir, "feed.xml"), rssXml, "utf-8");
  if (verbose) console.log("  feed.xml");

  if (verbose) console.log("Site built successfully.");
  return 0;
}
