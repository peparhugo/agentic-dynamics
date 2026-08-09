import fs from "node:fs/promises";
import path from "node:path";
import { glob } from "node:fs/promises";
import type { Page, SiteConfig, TemplateContext, TagIndexEntry } from "./types.js";
import { loadPage } from "./parser.js";
import { loadTemplates, renderPage, renderTagPage } from "./renderer.js";

export async function generateSite(config: SiteConfig): Promise<{ pages: Page[]; elapsed: number }> {
  const start = performance.now();

  await fs.mkdir(config.outputDir, { recursive: true });

  // Discover all markdown files
  const sourceFiles: string[] = [];
  for await (const entry of glob("**/*.md", { cwd: config.sourceDir })) {
    sourceFiles.push(path.join(config.sourceDir, entry));
  }

  // Parse all files in parallel (throughput optimization)
  const allPages = await Promise.all(
    sourceFiles.map((f) => loadPage(f, config.sourceDir, config.outputDir, config.baseUrl))
  );

  // Filter out drafts
  const pages = allPages.filter((p) => !p.frontmatter.draft);

  // Load templates
  const { layoutTemplate, pageTemplate, tagTemplate } = await loadTemplates(config.templateDir);

  // Build site context
  const siteCtx = {
    title: config.siteTitle,
    url: config.siteUrl,
    baseUrl: config.baseUrl,
  };

  // Build tag index
  const tagMap = new Map<string, Page[]>();
  for (const page of pages) {
    for (const tag of page.frontmatter.tags ?? []) {
      const existing = tagMap.get(tag);
      if (existing) {
        existing.push(page);
      } else {
        tagMap.set(tag, [page]);
      }
    }
  }
  const tags: TagIndexEntry[] = Array.from(tagMap.entries()).map(([tag, tagPages]) => ({
    tag,
    pages: tagPages,
  }));

  // Render and write page files in parallel
  await Promise.all(
    pages.map(async (page) => {
      const ctx: TemplateContext = {
        site: siteCtx,
        page: {
          title: page.frontmatter.title,
          date: page.frontmatter.date,
          tags: page.frontmatter.tags,
          content: page.html,
          url: page.url,
        },
        pages,
        tags,
      };
      const html = renderPage(pageTemplate, layoutTemplate, ctx);
      await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
      await fs.writeFile(page.outputPath, html, "utf-8");
    })
  );

  // Write tag index pages in parallel
  if (tagTemplate) {
    await Promise.all(
      tags.map(async (entry) => {
        const tagDir = path.join(config.outputDir, "tags", entry.tag);
        const tagOutPath = path.join(tagDir, "index.html");
        const ctx: TemplateContext = {
          site: siteCtx,
          page: {
            title: `Tag: ${entry.tag}`,
            content: "",
            url: `/tags/${entry.tag}/`,
          },
          pages,
          tags,
          currentTag: entry.tag,
        };
        const html = renderTagPage(tagTemplate, layoutTemplate, ctx);
        await fs.mkdir(tagDir, { recursive: true });
        await fs.writeFile(tagOutPath, html, "utf-8");
      })
    );
  }

  // Copy static assets from templateDir (CSS, JS, images, etc.)
  await copyStaticAssets(config.templateDir, config.outputDir);

  const elapsed = performance.now() - start;
  return { pages, elapsed };
}

async function copyStaticAssets(templateDir: string, outputDir: string): Promise<void> {
  const assetsDir = path.join(templateDir, "assets");
  try {
    await fs.access(assetsDir);
  } catch {
    return;
  }

  const destDir = path.join(outputDir, "assets");
  await fs.cp(assetsDir, destDir, { recursive: true });
}

export function injectReloadScript(html: string, port: number): string {
  const script = `<script>
(function(){
  var ws = new WebSocket('ws://localhost:${port}/__reload');
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') { location.reload(); }
  };
  ws.onclose = function() {
    setTimeout(function() {
      var w = new WebSocket('ws://localhost:${port}/__reload');
      w.onmessage = function(msg) {
        if (msg.data === 'reload') { location.reload(); }
      };
    }, 1000);
  };
})();
</script>`;
  return html.replace("</body>", script + "</body>");
}
