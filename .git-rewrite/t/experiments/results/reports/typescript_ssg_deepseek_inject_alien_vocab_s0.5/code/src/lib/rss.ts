import RSS from "rss";
import { BuildContext, Post } from "./types";

export function generateRssFeed(ctx: BuildContext): string {
  const published = ctx.posts.filter((p) => !p.frontmatter.draft);
  published.sort((a, b) => {
    const da = a.frontmatter.date ? new Date(a.frontmatter.date).getTime() : 0;
    const db = b.frontmatter.date ? new Date(b.frontmatter.date).getTime() : 0;
    return db - da;
  });

  const feed = new RSS({
    title: ctx.config.title,
    description: ctx.config.description,
    site_url: ctx.config.url,
    feed_url: `${ctx.config.url}/rss.xml`,
    language: ctx.config.language || "en",
    pubDate: published.length > 0
      ? published[0].frontmatter.date || new Date().toISOString()
      : new Date().toISOString(),
  });

  for (const post of published.slice(0, 20)) {
    feed.item({
      title: post.frontmatter.title || post.slug,
      description: post.html,
      url: `${ctx.config.url}${post.url}`,
      date: post.frontmatter.date || new Date().toISOString(),
      categories: post.frontmatter.tags,
    });
  }

  return feed.xml({ indent: true });
}
