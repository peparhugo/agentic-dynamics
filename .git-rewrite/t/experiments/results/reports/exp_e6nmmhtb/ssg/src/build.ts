import { readFile, writeFile, mkdir, readdir } from "node:fs/promises";
import { join, relative, dirname } from "node:path";
import { glob } from "node:fs/promises";
import { parseMarkdown } from "./markdown.js";
import { loadTemplates, renderPage } from "./templates.js";
import { generateRss } from "./rss.js";
import type { Page, BuildContext, SiteConfig } from "./types.js";

const LIVE_RELOAD_SCRIPT = `
<script>
(function(){
  if (window.__ssgLiveReload) return;
  window.__ssgLiveReload = true;
  var ws = new WebSocket('ws://' + location.hostname + ':35729');
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') location.reload();
  };
  ws.onclose = function() {
    setTimeout(function() {
      window.__ssgLiveReload = false;
    }, 2000);
  };
})();
</script>
`;

export async function buildSite(
  srcDir: string,
  templateDir: string,
  outDir: string,
  config: SiteConfig,
  injectReload = false,
): Promise<BuildContext> {
  const startTime = new Date();

  await loadTemplates(templateDir);

  const pattern = join(srcDir, "**/*.md").replace(/\\/g, "/");
  const files: string[] = [];
  for await (const f of glob(pattern)) {
    files.push(f);
  }

  const pages: Page[] = [];
  for (const file of files) {
    const raw = await readFile(file, "utf-8");
    const relPath = file.replace(srcDir, "").replace(/^[/\\]/, "");
    const page = parseMarkdown(raw, relPath);
    if (!page.frontmatter.draft || page.isPost) {
      pages.push(page);
    }
  }

  const tags = new Map<string, Page[]>();
  for (const page of pages) {
    for (const tag of page.frontmatter.tags ?? []) {
      const list = tags.get(tag) || [];
      list.push(page);
      tags.set(tag, list);
    }
  }

  const context: BuildContext = { pages, tags, config, startTime };

  for (const page of pages) {
    const html = renderPage(page, context);
    let fullHtml = html;
    if (injectReload) {
      fullHtml = html.replace("</body>", LIVE_RELOAD_SCRIPT + "</body>");
      if (fullHtml === html) {
        fullHtml = html + LIVE_RELOAD_SCRIPT;
      }
    }
    await writeOutput(outDir, page.url, fullHtml);
  }

  for (const [tag] of tags) {
    const tagUrl = `/tags/${tag}/`;
    const tagHtml = renderTagIndex(tag, context);
    let fullHtml = tagHtml;
    if (injectReload) {
      fullHtml = tagHtml.replace("</body>", LIVE_RELOAD_SCRIPT + "</body>");
      if (fullHtml === tagHtml) {
        fullHtml = tagHtml + LIVE_RELOAD_SCRIPT;
      }
    }
    await writeOutput(outDir, tagUrl, fullHtml);
  }

  const tagsIndexHtml = renderTagsIndex(context);
  let fullTagsHtml = tagsIndexHtml;
  if (injectReload) {
    fullTagsHtml = tagsIndexHtml.replace("</body>", LIVE_RELOAD_SCRIPT + "</body>");
    if (fullTagsHtml === tagsIndexHtml) {
      fullTagsHtml = tagsIndexHtml + LIVE_RELOAD_SCRIPT;
    }
  }
  await writeOutput(outDir, "/tags/", fullTagsHtml);

  const rss = generateRss(context);
  await writeOutput(outDir, "/feed.xml", rss, "application/xml");

  const notFoundHtml = renderNotFound(context);
  await writeOutput(outDir, "/404/", notFoundHtml);

  return context;
}

function renderTagIndex(tag: string, context: BuildContext): string {
  const tagged = (context.tags.get(tag) ?? []).filter(
    (p) => !p.frontmatter.draft,
  );
  const posts = tagged
    .filter((p) => p.frontmatter.date)
    .sort((a, b) => new Date(b.frontmatter.date!).getTime() - new Date(a.frontmatter.date!).getTime());

  const body = `
<h1>Tag: ${tag}</h1>
<ul>
${posts.map((p) => `<li><a href="${p.url}">${p.frontmatter.title}</a>${p.frontmatter.date ? ` — ${p.frontmatter.date}` : ""}</li>`).join("\n")}
</ul>
`;
  return body;
}

function renderTagsIndex(context: BuildContext): string {
  const entries = [...context.tags.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  const body = `
<h1>Tags</h1>
<ul>
${entries.map(([tag, pages]) => `<li><a href="/tags/${tag}/">${tag}</a> (${pages.length})</li>`).join("\n")}
</ul>
`;
  return body;
}

function renderNotFound(context: BuildContext): string {
  return `<h1>404 — Not Found</h1><p>The page you requested does not exist.</p>`;
}

async function writeOutput(
  outDir: string,
  url: string,
  content: string,
  mimeType = "text/html",
): Promise<void> {
  let dir = outDir;
  let filename = "index.html";

  if (url.endsWith(".xml")) {
    filename = url.split("/").pop()!;
    dir = join(outDir, ...url.split("/").slice(0, -1).filter(Boolean));
  } else {
    const parts = url.split("/").filter(Boolean);
    if (parts.length > 0) {
      dir = join(outDir, ...parts);
    }
  }

  await mkdir(dir, { recursive: true });
  await writeFile(join(dir, filename), content, "utf-8");
}
