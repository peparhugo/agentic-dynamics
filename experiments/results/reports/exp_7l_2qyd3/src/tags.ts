import type { Page } from "./types.js";

export interface TagInfo {
  tag: string;
  count: number;
  pages: Page[];
}

export function buildTagIndex(pages: Page[]): Map<string, TagInfo> {
  const map = new Map<string, TagInfo>();
  for (const page of pages) {
    for (const tag of page.frontmatter.tags ?? []) {
      if (!map.has(tag)) {
        map.set(tag, { tag, count: 0, pages: [] });
      }
      const info = map.get(tag)!;
      info.count++;
      info.pages.push(page);
    }
  }
  return map;
}

export function generateTagPages(
  tags: Map<string, TagInfo>,
  pages: Page[],
  renderTagPage: (tag: TagInfo, allPages: Page[]) => string
): Map<string, string> {
  const result = new Map<string, string>();
  for (const [tag, info] of tags) {
    const html = renderTagPage(info, pages);
    result.set(`tags/${tag}/index.html`, html);
  }
  return result;
}
