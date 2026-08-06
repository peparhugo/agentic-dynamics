import Handlebars from "handlebars";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { join, relative, dirname } from "node:path";
import { glob } from "node:fs/promises";
import type { Page, Site, SiteConfig, TagIndex } from "./types.js";
import { parseFile } from "./parser.js";
import {
  registerPartials,
  registerHelpers,
  loadLayouts,
  loadTemplate,
  buildSiteContext,
  markdownToHtml,
  renderPage,
} from "./renderer.js";
import { generateRSS } from "./feed.js";

export { markdownToHtml } from "./renderer.js";

function urlify(filePath: string): string {
  let url = filePath.replace(/\\/g, "/");
  url = url.replace(/\/index\.md$/, "/");
  url = url.replace(/\.md$/, ".html");
  if (!url.startsWith("/")) url = "/" + url;
  return url;
}

function collectTags(pages: Page[]): TagIndex[] {
  const map = new Map<string, Page[]>();
  for (const page of pages) {
    for (const tag of page.frontmatter.tags || []) {
      const normalized = tag.toLowerCase().trim();
      if (!map.has(normalized)) map.set(normalized, []);
      map.get(normalized)!.push(page);
    }
  }
  return Array.from(map.entries())
    .map(([tag, taggedPages]) => ({ tag, pages: taggedPages }))
    .sort((a, b) => a.tag.localeCompare(b.tag));
}

const fallbackTagTemplate = Handlebars.compile(`
<!DOCTYPE html>
<html><head><title>Tag: {{tag}}</title></head>
<body>
<h1>Posts tagged "{{tag}}"</h1>
<ul>{{#each pages}}<li><a href="{{url}}">{{frontmatter.title}}</a></li>{{/each}}</ul>
</body></html>`);

const fallbackIndexTemplate = Handlebars.compile(`
<!DOCTYPE html>
<html><head><title>{{config.siteTitle}}</title></head>
<body>
<h1>{{config.siteTitle}}</h1>
<ul>{{#each posts}}<li><a href="{{url}}">{{frontmatter.title}}</a> - {{frontmatter.date}}</li>{{/each}}</ul>
</body></html>`);

export async function build(config: SiteConfig): Promise<Site> {
  await registerPartials(config.templateDir);
  registerHelpers();
  const layouts = await loadLayouts(config.templateDir);

  const sourcePattern = join(config.sourceDir, "**/*.md");
  const mdFiles = await Array.fromAsync(glob(sourcePattern));

  const allPages: Page[] = [];
  const posts: Page[] = [];

  for (const mdFile of mdFiles) {
    const parsed = await parseFile(mdFile);
    if (parsed.frontmatter.draft) continue;

    const relPath = relative(config.sourceDir, mdFile);
    const url = urlify(relPath);
    const outputPath = join(config.outputDir, relPath.replace(/\.md$/, ".html"));
    const isPost = relPath.startsWith("posts/") || relPath.startsWith("blog/");
    const html = markdownToHtml(parsed.body);

    const page: Page = {
      frontmatter: parsed.frontmatter,
      content: parsed.body,
      html,
      url,
      sourcePath: mdFile,
      outputPath,
      isPost,
      template: isPost ? "post" : "page",
    };

    allPages.push(page);
    if (isPost) posts.push(page);
  }

  posts.sort((a, b) => {
    const da = a.frontmatter.date ? new Date(a.frontmatter.date).getTime() : 0;
    const db = b.frontmatter.date ? new Date(b.frontmatter.date).getTime() : 0;
    return db - da;
  });

  const tags = collectTags(posts);
  const site = buildSiteContext(allPages, posts, tags, config);

  for (const page of allPages) {
    const outDir = dirname(page.outputPath);
    await mkdir(outDir, { recursive: true });
    const rendered = await renderPage(page, site, layouts, config.templateDir);
    await writeFile(page.outputPath, rendered, "utf-8");
  }

  const tagTemplate = await loadTemplate(config.templateDir, "tag").catch(() => fallbackTagTemplate);

  for (const tag of tags) {
    const tagDir = join(config.outputDir, "tags", tag.tag);
    await mkdir(tagDir, { recursive: true });
    const layout = layouts.get("default");
    const inner = tagTemplate({ ...tag, site });
    const html = layout
      ? layout({ content: new Handlebars.SafeString(inner), tag, site })
      : inner;
    await writeFile(join(tagDir, "index.html"), html, "utf-8");
  }

  await mkdir(config.outputDir, { recursive: true });
  const indexTemplate = await loadTemplate(config.templateDir, "index").catch(() => fallbackIndexTemplate);

  const indexInner = indexTemplate({ posts: posts.slice(0, config.postsPerPage), site });
  const indexLayout = layouts.get("default");
  const indexHtml = indexLayout
    ? indexLayout({ content: new Handlebars.SafeString(indexInner), site })
    : indexInner;
  await writeFile(join(config.outputDir, "index.html"), indexHtml, "utf-8");

  const rss = generateRSS(site);
  await writeFile(join(config.outputDir, "rss.xml"), rss, "utf-8");

  return site;
}
