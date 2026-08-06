import * as fs from "node:fs";
import * as path from "node:path";
import { Page, SSGConfig, TemplateContext } from "./types.js";
import { parseFrontmatter } from "./frontmatter.js";
import { registerPartials, render } from "./renderer.js";
import { markdownToHtml } from "./highlight.js";
import { buildTagIndex } from "./tags.js";
import { generateRssXml } from "./rss.js";

export async function build(config: SSGConfig): Promise<void> {
  fs.mkdirSync(config.output, { recursive: true });

  registerPartials(path.join(config.templates, "partials"));

  const pages = collectPages(config.source);

  const tagData = buildTagIndex(pages);

  const baseContext: TemplateContext = {
    site: {
      title: config.siteTitle,
      url: config.siteUrl,
      description: config.siteDescription,
    },
    pages,
    tags: tagData,
  };

  const pageTemplate = path.join(config.templates, "page.hbs");

  for (const page of pages) {
    const ctx: TemplateContext = { ...baseContext, page };
    const html = render(pageTemplate, path.join(config.templates, "layouts"), ctx);
    const outPath = path.join(config.output, page.outputPath);
    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    fs.writeFileSync(outPath, html, "utf-8");
  }

  const indexTemplate = path.join(config.templates, "index.hbs");
  if (fs.existsSync(indexTemplate)) {
    const html = render(
      indexTemplate,
      path.join(config.templates, "layouts"),
      baseContext
    );
    fs.writeFileSync(path.join(config.output, "index.html"), html, "utf-8");
  }

  const tagTemplate = path.join(config.templates, "tag.hbs");
  if (fs.existsSync(tagTemplate)) {
    const tagsDir = path.join(config.output, "tags");
    fs.mkdirSync(tagsDir, { recursive: true });
    for (const td of tagData) {
      const ctx: TemplateContext = { ...baseContext, currentTag: td.tag, page: undefined, taggedPages: td.pages };
      const html = render(
        tagTemplate,
        path.join(config.templates, "layouts"),
        ctx
      );
      const safe = td.tag.replace(/[^a-zA-Z0-9-]/g, "-").toLowerCase();
      fs.writeFileSync(path.join(tagsDir, `${safe}.html`), html, "utf-8");
    }
  }

  const rss = generateRssXml(config, pages);
  fs.writeFileSync(path.join(config.output, "rss.xml"), rss, "utf-8");

  const css = `pre code.hljs{display:block;overflow-x:auto;padding:1em}code.hljs{padding:3px 5px}.hljs{background:#1e1e1e;color:#dcdcdc}.hljs-keyword,.hljs-literal,.hljs-symbol,.hljs-name{color:#569cd6}.hljs-type,.hljs-number{color:#b5cea8}.hljs-string{color:#d69d85}.hljs-comment{color:#6a9955}.hljs-meta{color:#9b9b9b}.hljs-attr,.hljs-built_in,.hljs-selector-tag,.hljs-title{color:#dcdcdc}`;
  fs.writeFileSync(path.join(config.output, "style.css"), css, "utf-8");
}

function collectPages(sourceDir: string): Page[] {
  const pages: Page[] = [];
  walk(sourceDir, (filePath) => {
    if (path.extname(filePath) !== ".md") return;
    const raw = fs.readFileSync(filePath, "utf-8");
    const { frontmatter, content } = parseFrontmatter(raw);
    const html = markdownToHtml(content);
    const relPath = path.relative(sourceDir, filePath);
    const slug = relPath.replace(/\.md$/, "").replace(/\\/g, "/");
    pages.push({
      frontmatter,
      content,
      html,
      raw,
      slug,
      sourcePath: filePath,
      outputPath: `${slug}.html`,
    });
  });
  return pages;
}

function walk(dir: string, fn: (filePath: string) => void): void {
  for (const entry of fs.readdirSync(dir)) {
    const full = path.join(dir, entry);
    if (fs.statSync(full).isDirectory()) {
      walk(full, fn);
    } else {
      fn(full);
    }
  }
}
