import fs from "node:fs/promises";
import path from "node:path";
import type { BuildOptions, Post, SiteData } from "./types.js";
import { loadPosts, buildTagIndex } from "./frontmatter.js";
import { loadTemplates, applyLayout } from "./render.js";
import { rssXml } from "./rss.js";

export async function build(options: BuildOptions): Promise<void> {
  await fs.rm(options.output, { recursive: true, force: true });
  await fs.mkdir(options.output, { recursive: true });

  const posts = await loadPosts(options.source, options.drafts);
  const tags = buildTagIndex(posts);

  const siteData: SiteData = {
    posts,
    tags,
    site: {
      title: options.siteTitle,
      description: options.siteDescription,
      url: options.siteUrl,
    },
  };

  const tpl = await loadTemplates(options.templates);

  for (const post of posts) {
    const body = tpl.post(
      { ...post, site: siteData.site },
      { allowProtoPropertiesByDefault: true }
    );
    const html = applyLayout(tpl, body, { title: post.frontmatter.title });
    await writePage(options.output, post.slug, html);
  }

  const indexBody = tpl.index(siteData, { allowProtoPropertiesByDefault: true });
  const indexHtml = applyLayout(tpl, indexBody, { title: options.siteTitle });
  await fs.writeFile(path.join(options.output, "index.html"), indexHtml);

  const tagsDir = path.join(options.output, "tags");
  await fs.mkdir(tagsDir, { recursive: true });
  for (const [tag, tagPosts] of Object.entries(tags)) {
    const tagBody = tpl.tag(
      { tag, posts: tagPosts, site: siteData.site },
      { allowProtoPropertiesByDefault: true }
    );
    const tagHtml = applyLayout(tpl, tagBody, { title: `Tag: ${tag}` });
    await fs.writeFile(path.join(tagsDir, `${tag}.html`), tagHtml);
  }

  // RSS: use template if available, otherwise programmatic
  const feed = tpl.rss
    ? tpl.rss(siteData, { allowProtoPropertiesByDefault: true })
    : rssXml(siteData);
  await fs.writeFile(path.join(options.output, "feed.xml"), feed);

  const assetsSrc = path.join(options.source, "assets");
  try {
    const assets = await fs.readdir(assetsSrc);
    const assetsDst = path.join(options.output, "assets");
    await fs.mkdir(assetsDst, { recursive: true });
    for (const asset of assets) {
      await fs.cp(path.join(assetsSrc, asset), path.join(assetsDst, asset), { recursive: true });
    }
  } catch {
    // No assets dir
  }

  console.log(
    `Built ${posts.length} posts, ${Object.keys(tags).length} tag pages to ${options.output}`
  );
}

async function writePage(output: string, slug: string, html: string): Promise<void> {
  const out = path.join(output, `${slug}.html`);
  await fs.writeFile(out, html);
}
