import { readdir, mkdir, writeFile, access } from "node:fs/promises";
import { join, relative, extname, dirname } from "node:path";
import type { Page, SiteConfig, TagInfo } from "./types.js";
import { readAndParse, isDraft, parseTags, parseDate } from "./frontmatter.js";
import { markdownToHtml } from "./highlight.js";
import { loadPartials, renderAllPages } from "./renderer.js";
import { generateRss } from "./rss.js";
import { buildTagIndex } from "./tags.js";

export async function discoverMarkdownFiles(
  dir: string
): Promise<string[]> {
  const results: string[] = [];
  const entries = await readdir(dir, { withFileTypes: true });
  await Promise.all(
    entries.map(async (entry) => {
      const fullPath = join(dir, entry.name);
      if (entry.isDirectory()) {
        const sub = await discoverMarkdownFiles(fullPath);
        results.push(...sub);
      } else if (entry.isFile() && extname(entry.name) === ".md") {
        results.push(fullPath);
      }
    })
  );
  return results;
}

export async function generate(config: SiteConfig): Promise<void> {
  await mkdir(config.outputDir, { recursive: true });

  await loadPartials(join(config.templateDir, "partials"));

  const files = await discoverMarkdownFiles(config.sourceDir);

  const pages: Page[] = await Promise.all(
    files.map(async (filePath) => {
      const rel = relative(config.sourceDir, filePath);
      const { data, content, slug } = await readAndParse(filePath);
      const html = markdownToHtml(content);
      const parentDir = dirname(rel);
      const url =
        parentDir === "."
          ? `/${slug}/index.html`
          : `/${parentDir}/${slug}/index.html`;

      return {
        path: filePath,
        frontmatter: data,
        content,
        html,
        url,
        isDraft: isDraft(data),
      };
    })
  );

  const tags = buildTagIndex(pages);
  const output = await renderAllPages(pages, config, tags);

  for (const [url, html] of output) {
    const outPath = join(config.outputDir, url);
    await mkdir(dirname(outPath), { recursive: true });
    await writeFile(outPath, html, "utf-8");
  }

  const rss = generateRss(pages, config);
  await writeFile(join(config.outputDir, "rss.xml"), rss, "utf-8");
}

export { Page, SiteConfig, TagInfo };
