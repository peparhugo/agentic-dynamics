import * as fs from "fs";
import * as path from "path";
import { GeneratorConfig, Page, TagIndex } from "./types";
import { parseFrontmatter, isPublished, pageUrl, sortByDate } from "./frontmatter";
import { renderMarkdown } from "./markdown";
import { TemplateEngine } from "./templates";
import { generateRss } from "./rss";

export class Generator {
  private config: GeneratorConfig;
  private engine: TemplateEngine;

  constructor(config: GeneratorConfig) {
    this.config = config;
    this.engine = new TemplateEngine(config.templateDir);
  }

  build(): Page[] {
    this.engine.load();

    this.prepareOutput();

    const pages = this.collectPages();
    const published = pages.filter((p) => isPublished(p.frontmatter)).sort(sortByDate);

    this.renderPages(published);
    this.copyAssets();

    const tags = this.collectTags(published);
    this.renderTagIndexes(tags, published);

    if (published.length > 0) {
      generateRss(
        published,
        this.config.siteTitle,
        this.config.siteUrl,
        this.config.outputDir,
      );
    }

    return published;
  }

  private prepareOutput(): void {
    if (fs.existsSync(this.config.outputDir)) {
      fs.rmSync(this.config.outputDir, { recursive: true, force: true });
    }
    fs.mkdirSync(this.config.outputDir, { recursive: true });
  }

  private collectPages(): Page[] {
    const pages: Page[] = [];
    this.walkDir(this.config.sourceDir, "", pages);
    return pages;
  }

  private walkDir(dir: string, relativePath: string, pages: Page[]): void {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      const relPath = relativePath ? path.join(relativePath, entry.name) : entry.name;

      if (entry.isDirectory()) {
        this.walkDir(fullPath, relPath, pages);
      } else if (entry.name.endsWith(".md")) {
        const raw = fs.readFileSync(fullPath, "utf-8");
        const { frontmatter, content } = parseFrontmatter(raw, fullPath);
        const html = renderMarkdown(content);
        const url = pageUrl(relPath);

        pages.push({
          path: relPath,
          url,
          frontmatter,
          content,
          html,
          raw,
        });
      }
    }
  }

  private renderPages(pages: Page[]): void {
    const siteContext = {
      title: this.config.siteTitle,
      url: this.config.siteUrl,
      pages: pages.map((p) => ({
        title: p.frontmatter.title,
        url: p.url,
        date: p.frontmatter.date,
        tags: p.frontmatter.tags,
        draft: p.frontmatter.draft,
      })),
      tags: [],
    };

    const pageTemplate = "page";
    const postTemplate = "post";
    const usedTemplate = this.engine.hasTemplate(postTemplate) ? postTemplate : pageTemplate;

    for (const page of pages) {
      const context = {
        page: {
          title: page.frontmatter.title,
          date: page.frontmatter.date,
          tags: page.frontmatter.tags,
          layout: page.frontmatter["layout"] as string | undefined,
        },
        site: siteContext,
        content: page.html,
        pages: siteContext.pages,
      };

      let html: string;
      try {
        html = this.engine.render(usedTemplate, context);
      } catch {
        html = this.engine.render(pageTemplate, context);
      }

      const outPath = path.join(this.config.outputDir, page.url.replace(/^\//, ""));
      fs.mkdirSync(path.dirname(outPath), { recursive: true });
      fs.writeFileSync(outPath, html);
    }

    const indexTemplate = "index";
    if (this.engine.hasTemplate(indexTemplate)) {
      const context = {
        page: { title: this.config.siteTitle },
        site: siteContext,
        pages: siteContext.pages,
        content: "",
      };
      const html = this.engine.render(indexTemplate, context);
      const outPath = path.join(this.config.outputDir, "index.html");
      fs.writeFileSync(outPath, html);
    }
  }

  private collectTags(pages: Page[]): TagIndex[] {
    const tagMap = new Map<string, Page[]>();
    for (const page of pages) {
      for (const tag of page.frontmatter.tags ?? []) {
        const tagKey = tag.toLowerCase();
        if (!tagMap.has(tagKey)) {
          tagMap.set(tagKey, []);
        }
        tagMap.get(tagKey)!.push(page);
      }
    }

    return Array.from(tagMap.entries())
      .map(([tag, tagPages]) => ({ tag, pages: tagPages.sort(sortByDate) }))
      .sort((a, b) => a.tag.localeCompare(b.tag));
  }

  private renderTagIndexes(tags: TagIndex[], allPages: Page[]): void {
    const tagTemplate = "tag";
    if (!this.engine.hasTemplate(tagTemplate)) {
      return;
    }

    const tagsDir = path.join(this.config.outputDir, "tags");
    fs.mkdirSync(tagsDir, { recursive: true });

    const siteContext = {
      title: this.config.siteTitle,
      url: this.config.siteUrl,
      pages: allPages.map((p) => ({
        title: p.frontmatter.title,
        url: p.url,
        date: p.frontmatter.date,
        tags: p.frontmatter.tags,
        draft: p.frontmatter.draft,
      })),
      tags: tags.map((t) => ({ tag: t.tag, count: t.pages.length })),
    };

    for (const tagIndex of tags) {
      const context = {
        page: { title: `Tag: ${tagIndex.tag}` },
        site: siteContext,
        tag: tagIndex.tag,
        pages: tagIndex.pages.map((p) => ({
          title: p.frontmatter.title,
          url: p.url,
          date: p.frontmatter.date,
          tags: p.frontmatter.tags,
        })),
        tags: siteContext.tags,
        content: "",
      };

      const html = this.engine.render(tagTemplate, context);
      const outPath = path.join(tagsDir, `${tagIndex.tag}.html`);
      fs.writeFileSync(outPath, html);
    }
  }

  private copyAssets(): void {
    const assetsDir = path.join(this.config.sourceDir, "assets");
    if (fs.existsSync(assetsDir)) {
      this.copyDir(assetsDir, this.config.outputDir);
    }
  }

  private copyDir(src: string, dest: string): void {
    fs.mkdirSync(dest, { recursive: true });
    const entries = fs.readdirSync(src, { withFileTypes: true });
    for (const entry of entries) {
      const srcPath = path.join(src, entry.name);
      const destPath = path.join(dest, entry.name);
      if (entry.isDirectory()) {
        this.copyDir(srcPath, destPath);
      } else {
        fs.copyFileSync(srcPath, destPath);
      }
    }
  }
}
