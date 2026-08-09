import type { Page, TagInfo } from "./types.js";
import { parseTags } from "./frontmatter.js";

export function buildTagIndex(pages: Page[]): TagInfo[] {
  const tagMap = new Map<string, Page[]>();

  for (const page of pages) {
    if (page.isDraft) continue;
    const tags = parseTags(page.frontmatter);
    for (const tag of tags) {
      const list = tagMap.get(tag) ?? [];
      list.push(page);
      tagMap.set(tag, list);
    }
  }

  const result: TagInfo[] = [];
  for (const [name, tagPages] of tagMap) {
    tagPages.sort(
      (a, b) =>
        new Date(b.frontmatter.date ?? 0).getTime() -
        new Date(a.frontmatter.date ?? 0).getTime()
    );
    result.push({ name, pages: tagPages, count: tagPages.length });
  }

  result.sort((a, b) => b.count - a.count);
  return result;
}
