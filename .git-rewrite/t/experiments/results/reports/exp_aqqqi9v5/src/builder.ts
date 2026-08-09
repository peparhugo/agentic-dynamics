import fs from "node:fs/promises";
import path from "node:path";
import { glob } from "node:fs/promises";
import type { SiteConfig, Page } from "./types.js";
import { parseFile } from "./parser.js";
import { renderMarkdown } from "./renderer.js";
import { compileTemplates, renderPage, renderTagPage, renderIndex } from "./template.js";
import { buildTagIndex, tagIndexToArray } from "./tags.js";
import { generateRSS } from "./rss.js";

async function collectPages(
  sourceDir: string,
  outputDir: string,
): Promise<Page[]> {
  const pages: Page[] = [];
  const pattern = path.join(sourceDir, "**/*.md");
  const files = glob(pattern);

  for await (const file of files) {
    const page = await parseFile(file, sourceDir, outputDir);
    pages.push(page);
  }

  return pages.sort((a, b) => {
    const da = a.frontmatter.date ?? "";
    const db = b.frontmatter.date ?? "";
    return db.localeCompare(da);
  });
}

export async function buildSite(config: SiteConfig): Promise<void> {
  await fs.mkdir(config.outputDir, { recursive: true });

  const pages = await collectPages(config.sourceDir, config.outputDir);

  for (const page of pages) {
    page.html = renderMarkdown(page.content);
  }

  const { templates } = await compileTemplates(config.templateDir);
  const mainTemplate =
    templates.get("layout") ??
    templates.get("default") ??
    templates.get("post") ??
    [...templates.values()][0];

  if (!mainTemplate) {
    throw new Error(
      `No template found in ${config.templateDir}. Add a layout.hbs, default.hbs, or post.hbs template.`,
    );
  }

  const published = pages.filter((p) => !p.isDraft);

  // Render individual pages
  for (const page of published) {
    const html = renderPage(page, mainTemplate, pages, config);
    const dir = path.dirname(page.outputPath);
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(page.outputPath, html);
  }

  // Render index page
  const indexTemplate = templates.get("index");
  if (indexTemplate) {
    const indexHtml = renderIndex(pages, indexTemplate, config);
    await fs.writeFile(path.join(config.outputDir, "index.html"), indexHtml);
  }

  // Render tag pages
  const tagTemplate = templates.get("tag");
  const tagMap = buildTagIndex(pages);
  if (tagTemplate) {
    const tagDir = path.join(config.outputDir, "tags");
    await fs.mkdir(tagDir, { recursive: true });
    for (const tagIndex of tagIndexToArray(tagMap)) {
      const html = renderTagPage(tagIndex, tagTemplate, config);
      const safeTag = tagIndex.tag.replace(/[^a-zA-Z0-9-]/g, "-");
      await fs.writeFile(path.join(tagDir, `${safeTag}.html`), html);
    }
  }

  // Generate RSS
  const feed = generateRSS(pages, config);
  await fs.writeFile(path.join(config.outputDir, "rss.xml"), feed);

  console.log(
    `Built ${published.length} page(s), ${tagMap.size} tag(s) to ${config.outputDir}`,
  );
}
