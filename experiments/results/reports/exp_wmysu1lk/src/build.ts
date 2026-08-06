import fs from "node:fs";
import path from "node:path";
import { parseFrontmatter } from "./frontmatter";
import { renderTemplate } from "./render";
import { markdownToHtml } from "./highlight";
import { buildTagIndex, tagsTemplateData } from "./tags";
import { generateRssXml } from "./rss";
import { Post, SiteConfig, TemplateData } from "./types";

export interface BuildOptions {
  sourceDir: string;
  templateDir: string;
  outputDir: string;
  config: SiteConfig;
}

export function build(options: BuildOptions): number {
  const { sourceDir, templateDir, outputDir, config } = options;

  fs.mkdirSync(outputDir, { recursive: true });

  const posts = loadPosts(sourceDir);
  const published = posts.filter((p) => !p.draft);
  published.sort((a, b) => b.date.localeCompare(a.date));

  const tagIndex = buildTagIndex(published);
  const tags = tagsTemplateData(tagIndex);

  const baseData: TemplateData = {
    site: config,
    posts: published,
    tags,
  };

  const indexHtml = renderTemplate(templateDir, "index", baseData);
  fs.writeFileSync(path.join(outputDir, "index.html"), indexHtml);

  fs.mkdirSync(path.join(outputDir, "tags"), { recursive: true });
  for (const tag of tags) {
    const tagData: TemplateData = {
      site: config,
      posts: tag.posts,
      tags,
    };
    const html = renderTemplate(templateDir, "tag", tagData);
    fs.mkdirSync(path.join(outputDir, "tags", tag.name), { recursive: true });
    fs.writeFileSync(
      path.join(outputDir, "tags", tag.name, "index.html"),
      html
    );
  }

  const tagsIndexHtml = renderTemplate(templateDir, "tags-index", baseData);
  fs.writeFileSync(path.join(outputDir, "tags", "index.html"), tagsIndexHtml);

  fs.mkdirSync(path.join(outputDir, "posts"), { recursive: true });
  for (const post of published) {
    const htmlContent = markdownToHtml(post.content);
    const postData: TemplateData = {
      site: config,
      posts: published,
      post: { ...post, content: htmlContent },
      tags,
    };
    const html = renderTemplate(templateDir, "post", postData);
    fs.mkdirSync(path.join(outputDir, "posts", post.slug), { recursive: true });
    fs.writeFileSync(
      path.join(outputDir, "posts", post.slug, "index.html"),
      html
    );
  }

  const rssXml = generateRssXml(config, published);
  fs.writeFileSync(path.join(outputDir, "feed.xml"), rssXml);

  fs.writeFileSync(
    path.join(outputDir, "site.json"),
    JSON.stringify(config, null, 2)
  );

  return published.length;
}

function loadPosts(dir: string): Post[] {
  const posts: Post[] = [];
  for (const file of fs.readdirSync(dir)) {
    if (!file.endsWith(".md")) continue;
    const filePath = path.join(dir, file);
    const parsed = parseFrontmatter(filePath);
    if (!parsed) continue;
    const { frontmatter, content } = parsed;
    posts.push({
      title: frontmatter.title ?? "Untitled",
      date: frontmatter.date ?? new Date().toISOString().split("T")[0],
      tags: frontmatter.tags ?? [],
      draft: frontmatter.draft ?? false,
      slug: path.basename(file, ".md"),
      content,
      excerpt: content.slice(0, 200).replace(/\n/g, " "),
    });
  }
  return posts;
}
