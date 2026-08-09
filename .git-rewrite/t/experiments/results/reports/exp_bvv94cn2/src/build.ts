import { join, extname, dirname, relative } from "node:path";
import { readFile } from "node:fs/promises";
import type { Page, SiteConfig, BuildResult } from "./types.js";
import { parseFrontmatter } from "./frontmatter.js";
import { markdownToHtml } from "./markdown.js";
import { createEngine, type TemplateEngine } from "./templates.js";
import { buildTagIndexes } from "./tags.js";
import { generateRss } from "./rss.js";
import { walkDir, writeTextFile, copyDir, ensureDir, pathToUrl } from "./utils.js";

export async function build(config: SiteConfig): Promise<BuildResult> {
  const errors: string[] = [];
  const engine = await createEngine(config.templateDir);
  const pages: Page[] = [];

  // Read all markdown files
  for await (const filePath of walkDir(config.sourceDir)) {
    if (extname(filePath) !== ".md") continue;

    try {
      const raw = await readFile(filePath, "utf-8");
      const { frontmatter, body } = parseFrontmatter(raw);
      const htmlContent = markdownToHtml(body);
      const url = pathToUrl(filePath, config.sourceDir);

      pages.push({
        path: filePath,
        sourcePath: relative(config.sourceDir, filePath),
        frontmatter,
        content: body,
        html: htmlContent,
        url,
      });
    } catch (err) {
      errors.push(`Error processing ${filePath}: ${String(err)}`);
    }
  }

  // Sort by date descending
  pages.sort((a, b) => {
    const da = String(a.frontmatter.date ?? "");
    const db = String(b.frontmatter.date ?? "");
    return db.localeCompare(da);
  });

  // Build tag indexes
  const tags = buildTagIndexes(pages);

  // Load templates
  let pageTemplate = "";
  let indexTemplate = "";
  let tagTemplate = "";
  try {
    pageTemplate = await readFile(join(config.templateDir, "post.hbs"), "utf-8");
  } catch {
    // Template optional
  }
  try {
    indexTemplate = await readFile(join(config.templateDir, "index.hbs"), "utf-8");
  } catch {
    // Template optional
  }
  try {
    tagTemplate = await readFile(join(config.templateDir, "tag.hbs"), "utf-8");
  } catch {
    // Template optional
  }

  // Render page files
  for (const page of pages) {
    if (page.frontmatter.draft) continue;

    const template = page.frontmatter.layout
      ? await loadTemplate(config.templateDir, page.frontmatter.layout)
      : pageTemplate;

    if (!template) continue;

    const html = engine.renderPage(
      template,
      {
        page,
        pages,
        tags,
        config,
        title: page.frontmatter.title,
        date: page.frontmatter.date,
        content: page.html,
      },
      page.frontmatter.layout ? undefined : undefined
    );

    const outPath = join(config.outputDir, page.url === "/" ? "index.html" : page.url + "index.html");
    await writeTextFile(outPath, html);
  }

  // Render index page
  if (indexTemplate) {
    const publicPages = pages.filter(p => !p.frontmatter.draft);
    const indexHtml = engine.renderPage(indexTemplate, {
      pages: publicPages,
      tags,
      config,
      title: config.siteTitle,
    });
    await writeTextFile(join(config.outputDir, "index.html"), indexHtml);
  }

  // Render tag pages
  if (tagTemplate) {
    for (const tagIndex of tags) {
      const tagHtml = engine.renderPage(tagTemplate, {
        tag: tagIndex,
        pages: tagIndex.pages,
        tags,
        config,
        title: `Tag: ${tagIndex.tag}`,
      });
      await writeTextFile(
        join(config.outputDir, "tags", tagIndex.tag, "index.html"),
        tagHtml
      );
    }
  }

  // RSS feed
  const rss = generateRss(pages, config);
  await writeTextFile(join(config.outputDir, "feed.xml"), rss);

  // Copy static assets (non-.md files)
  for await (const filePath of walkDir(config.sourceDir)) {
    if (extname(filePath) === ".md") continue;
    const rel = relative(config.sourceDir, filePath);
    const dest = join(config.outputDir, rel);
    await writeTextFile(dest, await readFile(filePath, "utf-8"));
  }

  return { pages, tags, errors };
}

async function loadTemplate(templateDir: string, name: string): Promise<string> {
  try {
    return await readFile(join(templateDir, `${name}.hbs`), "utf-8");
  } catch {
    return "";
  }
}
