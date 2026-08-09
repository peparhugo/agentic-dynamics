import fs from "fs";
import path from "path";
import { GeneratorOptions, Page } from "./types";
import { collectMarkdownFiles, parseFrontmatter, deriveUrlPath } from "./parser";
import { configureTemplateEngine, renderPage, buildTagMap, generateTagIndex } from "./renderer";
import { configureMarked, markdownToHtml } from "./highlight";
import { generateRss } from "./rss";

export function buildSite(options: GeneratorOptions): void {
  configureMarked();

  const layout = configureTemplateEngine(options.templateDir);
  const markdownFiles = collectMarkdownFiles(options.sourceDir);

  const pages: Page[] = [];
  for (const f of markdownFiles) {
    const { frontmatter, content } = parseFrontmatter(f);
    const urlPath = deriveUrlPath(f, options.sourceDir);
    const html = markdownToHtml(content);
    pages.push({ path: urlPath, sourcePath: f, frontmatter, content, html });
  }

  // Print summary
  const drafts = pages.filter(p => p.frontmatter.draft);
  const published = pages.filter(p => !p.frontmatter.draft);
  console.log(`Found ${pages.length} pages (${published.length} published, ${drafts.length} drafts)`);

  // Ensure output directory exists
  if (fs.existsSync(options.outputDir)) {
    fs.rmSync(options.outputDir, { recursive: true });
  }
  fs.mkdirSync(options.outputDir, { recursive: true });

  // Render each published page
  for (const p of published) {
    const rendered = renderPage(p, pages, options.templateDir, layout, options);
    writeOutput(options.outputDir, p.path, rendered);
    console.log(`  -> ${p.path}`);
  }

  // Tag index pages
  const tagMap = buildTagMap(published);
  for (const [tag, taggedPages] of tagMap) {
    const rendered = generateTagIndex(tag, taggedPages, layout, options);
    const tagPath = `/tags/${slugify(tag)}/`;
    writeOutput(options.outputDir, tagPath, rendered);
    console.log(`  -> ${tagPath} (${taggedPages.length} pages)`);
  }

  // RSS feed
  const rss = generateRss(published, options.config);
  writeOutput(options.outputDir, "/feed.xml", rss);
  console.log(`  -> /feed.xml`);
}

function writeOutput(outDir: string, urlPath: string, html: string): void {
  // Normalize: remove leading /, treat trailing / as index.html
  let rel = urlPath.replace(/^\/+/, "");
  if (!rel || rel.endsWith("/")) {
    rel = rel + "index.html";
  }
  const outPath = path.join(outDir, rel);
  const dir = path.dirname(outPath);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(outPath, html);
}

function slugify(tag: string): string {
  return tag.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}
