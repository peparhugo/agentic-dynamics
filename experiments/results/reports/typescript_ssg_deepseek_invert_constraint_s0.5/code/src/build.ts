import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join, relative, basename } from "node:path";
import Handlebars from "handlebars";
import {
  parseFrontmatter,
  renderMarkdown,
  ensureDir,
  collectFiles,
  copyFile,
} from "./utils.js";
import type { Post, TemplateContext, BuilderOptions } from "./types.js";

export function build(opts: BuilderOptions): { posts: Post[]; tagPages: string[] } {
  const { sourceDir, templateDir, outputDir, baseUrl, siteTitle, siteDescription } = opts;

  ensureDir(outputDir);

  Handlebars.registerHelper("formatDate", (d: Date | undefined) => {
    if (!d) return "";
    return d.toISOString().split("T")[0];
  });

  const partialsDir = join(templateDir, "partials");
  if (existsSync(partialsDir)) {
    for (const f of collectFiles(partialsDir, ".hbs")) {
      const name = basename(f, ".hbs");
      Handlebars.registerPartial(name, readFileSync(f, "utf-8"));
    }
  }

  const layoutFile = join(templateDir, "layout.hbs");
  const layoutSrc = readFileSync(layoutFile, "utf-8");
  const layout = Handlebars.compile(layoutSrc);

  const postTemplateFile = join(templateDir, "post.hbs");
  const postTemplateSrc = readFileSync(postTemplateFile, "utf-8");
  const postTemplate = Handlebars.compile(postTemplateSrc);

  const indexTemplateFile = join(templateDir, "index.hbs");
  const indexTemplateSrc = readFileSync(indexTemplateFile, "utf-8");
  const indexTemplate = Handlebars.compile(indexTemplateSrc);

  const tagTemplateFile = join(templateDir, "tag.hbs");
  const tagTemplateSrc = readFileSync(tagTemplateFile, "utf-8");
  const tagTemplate = Handlebars.compile(tagTemplateSrc);

  const mds = collectFiles(sourceDir, ".md");
  const posts: Post[] = mds
    .map(parseFrontmatter)
    .filter((p) => !p.draft)
    .sort((a, b) => (b.date?.getTime() ?? 0) - (a.date?.getTime() ?? 0));

  const ctx: TemplateContext = {
    posts,
    site: { title: siteTitle, description: siteDescription, baseUrl },
  };

  const renderedPosts: Post[] = posts.map((p) => ({
    ...p,
    content: renderMarkdown(p.content),
  }));

  const tagMap = new Map<string, Post[]>();
  for (const p of renderedPosts) {
    for (const tag of p.tags) {
      const list = tagMap.get(tag) ?? [];
      list.push(p);
      tagMap.set(tag, list);
    }
  }

  const indexHtml = layout({ ...ctx, body: indexTemplate({ ...ctx, posts: renderedPosts }) });
  writeFileSync(join(outputDir, "index.html"), indexHtml);

  for (const post of renderedPosts) {
    const postHtml = layout({
      ...ctx,
      page: { title: post.title },
      body: postTemplate({ ...ctx, post }),
    });
    const outDir = join(outputDir, post.slug);
    ensureDir(outDir);
    writeFileSync(join(outDir, "index.html"), postHtml);
  }

  const tagsDir = join(outputDir, "tags");
  ensureDir(tagsDir);
  for (const [tag, tagged] of tagMap) {
    const tagHtml = layout({
      ...ctx,
      page: { title: `Tag: ${tag}`, tag },
      body: tagTemplate({ ...ctx, posts: tagged, page: { tag } }),
    });
    const tagOut = join(tagsDir, tag);
    ensureDir(tagOut);
    writeFileSync(join(tagOut, "index.html"), tagHtml);
  }

  const staticDir = join(templateDir, "static");
  if (existsSync(staticDir)) {
    for (const f of collectFiles(staticDir, "")) {
      const rel = relative(staticDir, f);
      copyFile(f, join(outputDir, rel));
    }
  }

  return { posts: renderedPosts, tagPages: [...tagMap.keys()] };
}
