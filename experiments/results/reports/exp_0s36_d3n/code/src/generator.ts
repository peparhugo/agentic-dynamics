import fs from "fs";
import path from "path";
import { Page, SiteConfig, TemplateContext, TagIndexContext } from "./types";
import { resolvePages, getPublishedPages, getSortedPages, getTags } from "./frontmatter";
import { renderMarkdown } from "./markdown";
import { createTemplateEngine } from "./templates";
import { generateRSS } from "./rss";

export interface GeneratorOptions {
  sourceDir: string;
  templateDir: string;
  outputDir: string;
  siteConfig: SiteConfig;
}

export function generate(options: GeneratorOptions): void {
  const { sourceDir, templateDir, outputDir, siteConfig } = options;
  const engine = createTemplateEngine(templateDir);

  if (fs.existsSync(outputDir)) {
    fs.rmSync(outputDir, { recursive: true });
  }
  fs.mkdirSync(outputDir, { recursive: true });

  const allPages = resolvePages(sourceDir);
  const publishedPages = getPublishedPages(allPages);

  for (const page of publishedPages) {
    page.html = renderMarkdown(page.content);
  }

  const sortedPages = getSortedPages(publishedPages);

  for (const page of publishedPages) {
    const templateName = page.frontmatter.layout || "post";
    const layoutName = "layouts/default";
    const context: TemplateContext = {
      title: page.frontmatter.title,
      date: page.frontmatter.date,
      tags: page.frontmatter.tags,
      content: page.html,
      page,
      pages: sortedPages,
      site: siteConfig,
    };

    let html: string;
    try {
      html = engine.renderWithLayout(templateName, layoutName, context);
    } catch {
      html = engine.render(templateName, context);
    }

    const outPath = path.join(outputDir, page.url);
    fs.mkdirSync(outPath, { recursive: true });
    fs.writeFileSync(path.join(outPath, "index.html"), html);
  }

  copyStaticAssets(templateDir, outputDir);

  const tags = getTags(sortedPages);
  if (tags.size > 0) {
    const tagsDir = path.join(outputDir, "tags");
    fs.mkdirSync(tagsDir, { recursive: true });

    for (const [tag, tagPages] of tags) {
      const context: TagIndexContext = {
        tag,
        posts: tagPages,
        site: siteConfig,
        title: `Posts tagged "${tag}"`,
        pages: sortedPages,
      };

      let html: string;
      try {
        html = engine.renderWithLayout("tag", "layouts/default", context);
      } catch {
        html = engine.render("tag", context);
      }

      const tagOutDir = path.join(tagsDir, tag);
      fs.mkdirSync(tagOutDir, { recursive: true });
      fs.writeFileSync(path.join(tagOutDir, "index.html"), html);
    }
  }

  if (sortedPages.length > 0) {
    const feed = generateRSS(sortedPages, siteConfig, siteConfig.url);
    fs.writeFileSync(path.join(outputDir, "feed.xml"), feed);
  }
}

function copyStaticAssets(templateDir: string, outputDir: string): void {
  const assetsDir = path.join(templateDir, "assets");
  if (!fs.existsSync(assetsDir)) return;
  copyRecursive(assetsDir, outputDir);
}

function copyRecursive(src: string, dest: string): void {
  fs.mkdirSync(dest, { recursive: true });
  const entries = fs.readdirSync(src, { withFileTypes: true });
  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyRecursive(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}
