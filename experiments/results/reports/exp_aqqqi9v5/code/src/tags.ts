import type { Page, TagIndex } from "./types.js";

export function buildTagIndex(pages: Page[]): Map<string, Page[]> {
  const map = new Map<string, Page[]>();

  for (const page of pages) {
    if (page.isDraft) continue;
    const tags = page.frontmatter.tags ?? [];
    for (const tag of tags) {
      const existing = map.get(tag);
      if (existing) {
        existing.push(page);
      } else {
        map.set(tag, [page]);
      }
    }
  }

  return map;
}

export function tagIndexToArray(map: Map<string, Page[]>): TagIndex[] {
  return [...map.entries()].map(([tag, pages]) => ({ tag, pages }));
}
