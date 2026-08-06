import { Page, TagMap, SiteConfig } from "./types.js";

export function buildTagMap(pages: Page[]): TagMap {
  const map: TagMap = {};

  for (const page of pages) {
    if (page.frontmatter.draft) continue;
    const tags = page.frontmatter.tags ?? [];
    for (const tag of tags) {
      if (!map[tag]) map[tag] = [];
      map[tag].push(page);
    }
  }

  return map;
}

export function generateTagPages(
  tagMap: TagMap,
  renderPage: (page: Page, pages: Page[]) => string,
  _config: SiteConfig
): Page[] {
  const tagPages: Page[] = [];
  const allPages = Object.values(tagMap).flat();

  for (const [tag, pages] of Object.entries(tagMap)) {
    const listHtml = pages
      .map((p) => `<li><a href="/${p.url}">${p.frontmatter.title}</a></li>`)
      .join("\n");

    const fullHtml = `<h1>Tag: ${tag}</h1>\n<ul>\n${listHtml}\n</ul>`;

    const tagPage: Page = {
      path: `tags/${slugify(tag)}.html`,
      frontmatter: {
        title: `Tag: ${tag}`,
        layout: "default",
      },
      content: "",
      html: fullHtml,
      url: `tags/${slugify(tag)}.html`,
    };

    tagPages.push(tagPage);
  }

  return tagPages.map((p) => ({
    ...p,
    html: renderPage(p, allPages),
  }));
}

function slugify(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}
