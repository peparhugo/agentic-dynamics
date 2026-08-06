import RSS from "rss";
import type { Page, BuildContext } from "./types.js";

export function generateRss(context: BuildContext): string {
  const posts = context.pages
    .filter((p) => p.isPost && !p.frontmatter.draft && p.frontmatter.date)
    .sort((a, b) => {
      const da = new Date(a.frontmatter.date!).getTime();
      const db = new Date(b.frontmatter.date!).getTime();
      return db - da;
    });

  const feed = new RSS({
    title: context.config.title,
    description: context.config.description,
    feed_url: `${context.config.baseUrl}/feed.xml`,
    site_url: context.config.baseUrl,
    language: context.config.language,
    pubDate: posts[0]?.frontmatter.date ?? new Date().toISOString(),
  });

  for (const post of posts) {
    feed.item({
      title: post.frontmatter.title,
      description: post.html,
      url: `${context.config.baseUrl}${post.url}`,
      date: post.frontmatter.date,
      categories: post.frontmatter.tags,
      author: post.frontmatter.author as string | undefined,
    });
  }

  return feed.xml({ indent: true });
}
