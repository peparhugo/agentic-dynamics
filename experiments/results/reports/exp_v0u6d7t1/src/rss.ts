import Handlebars from "handlebars";
import fs from "node:fs/promises";
import path from "node:path";
import type { BuildContext, Page } from "./types.js";

export async function generateRssFeed(
  ctx: BuildContext,
  templatesDir: string,
): Promise<string> {
  const rssPath = path.join(templatesDir, "rss.hbs");
  let template: string;
  try {
    template = await fs.readFile(rssPath, "utf-8");
  } catch {
    template = defaultRssTemplate();
  }

  const compiled = Handlebars.compile(template);
  const posts = ctx.publishedPages
    .filter((p) => p.frontmatter.date)
    .sort((a, b) =>
      new Date(b.frontmatter.date!).getTime() -
      new Date(a.frontmatter.date!).getTime(),
    )
    .slice(0, 20);

  return compiled({
    site: { title: ctx.siteTitle, url: ctx.siteUrl },
    posts: posts.map((p) => ({
      title: p.frontmatter.title,
      url: ctx.siteUrl + p.url,
      date: p.frontmatter.date,
      html: p.html,
      rfc822Date: p.frontmatter.date
        ? new Date(p.frontmatter.date).toUTCString()
        : "",
    })),
    now: new Date().toUTCString(),
  });
}

function defaultRssTemplate(): string {
  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{{site.title}}</title>
    <link>{{site.url}}</link>
    <description>{{site.title}}</description>
    <atom:link href="{{site.url}}/feed.xml" rel="self" type="application/rss+xml"/>
    <lastBuildDate>{{now}}</lastBuildDate>
{{#each posts}}
    <item>
      <title>{{title}}</title>
      <link>{{url}}</link>
      <guid isPermaLink="true">{{url}}</guid>
      <pubDate>{{rfc822Date}}</pubDate>
      <description><![CDATA[{{{html}}}]]></description>
    </item>
{{/each}}
  </channel>
</rss>`;
}
