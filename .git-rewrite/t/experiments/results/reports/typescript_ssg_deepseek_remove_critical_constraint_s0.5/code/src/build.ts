import fs from "node:fs";
import path from "node:path";
import { markdownToHtml } from "./markdown";
import { HandlebarsTemplateEngine } from "./templates";
import { isValidPage, collectPages } from "./frontmatter";
import { buildTagData } from "./tags";
import { generateRss } from "./rss";
import { Page, SiteConfig, TemplateContext, TagData } from "./types";

const RELOAD_SCRIPT = `
<script>
(function() {
  var ws = new WebSocket('ws://' + location.host + '/__livereload');
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') location.reload();
  };
  ws.onclose = function() {
    setTimeout(function() {
      window.location.reload();
    }, 2000);
  };
})();
</script>`;

export async function build(config: SiteConfig, injectReload = false): Promise<void> {
  const engine = new HandlebarsTemplateEngine(config.templateDir);

  fs.mkdirSync(config.outputDir, { recursive: true });

  const allPages = await collectPages(config.sourceDir);
  const pages = allPages.filter((p) => isValidPage(p.frontmatter));

  for (const page of pages) {
    page.html = markdownToHtml(page.content);
  }

  const sortedPages = [...pages].sort((a, b) => {
    const da = a.frontmatter.date ?? "";
    const db = b.frontmatter.date ?? "";
    return db.localeCompare(da);
  });

  const tags = buildTagData(pages);

  const siteContext = { title: config.siteTitle, url: config.siteUrl };

  for (const page of pages) {
    const context: TemplateContext = {
      page,
      pages: sortedPages,
      tags,
      site: siteContext,
    };
    let html = engine.render("post", context);
    if (injectReload) {
      html = html.replace("</body>", `${RELOAD_SCRIPT}</body>`);
    }
    const outDir = path.join(config.outputDir, page.slug);
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(path.join(outDir, "index.html"), html);
  }

  if (fs.existsSync(path.join(config.templateDir, "index.hbs")) || fs.existsSync(path.join(config.templateDir, "index.handlebars"))) {
    const indexContext: TemplateContext = {
      pages: sortedPages,
      tags,
      site: siteContext,
    };
    let indexHtml = engine.render("index", indexContext);
    if (injectReload) {
      indexHtml = indexHtml.replace("</body>", `${RELOAD_SCRIPT}</body>`);
    }
    fs.writeFileSync(path.join(config.outputDir, "index.html"), indexHtml);
  }

  if (fs.existsSync(path.join(config.templateDir, "tag.hbs")) || fs.existsSync(path.join(config.templateDir, "tag.handlebars"))) {
    const tagsDir = path.join(config.outputDir, "tags");
    fs.mkdirSync(tagsDir, { recursive: true });

    for (const tagData of tags) {
      const tagContext: TemplateContext = {
        tag: tagData.tag,
        pages: tagData.pages,
        tags,
        site: siteContext,
      } as TemplateContext;
      let tagHtml = engine.render("tag", tagContext);
      if (injectReload) {
        tagHtml = tagHtml.replace("</body>", `${RELOAD_SCRIPT}</body>`);
      }
      fs.writeFileSync(path.join(tagsDir, `${tagData.tag}.html`), tagHtml);
    }
  }

  const rssContent = generateRss(pages, config);
  fs.writeFileSync(path.join(config.outputDir, "rss.xml"), rssContent);

  copyStaticAssets(config.templateDir, config.outputDir);
}

function copyStaticAssets(templateDir: string, outputDir: string) {
  const staticDir = path.join(templateDir, "static");
  if (!fs.existsSync(staticDir)) return;
  copyRecursive(staticDir, outputDir);
}

function copyRecursive(src: string, dest: string) {
  const entries = fs.readdirSync(src, { withFileTypes: true });
  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      fs.mkdirSync(destPath, { recursive: true });
      copyRecursive(srcPath, destPath);
    } else {
      fs.mkdirSync(path.dirname(destPath), { recursive: true });
      fs.copyFileSync(srcPath, destPath);
    }
  }
}
