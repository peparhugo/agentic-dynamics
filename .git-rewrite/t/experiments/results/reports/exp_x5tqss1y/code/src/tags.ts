import { Page, TagData } from "./types.js";

export function buildTagIndex(pages: Page[]): TagData[] {
  const map = new Map<string, Page[]>();
  for (const page of pages) {
    for (const tag of page.frontmatter.tags ?? []) {
      if (!map.has(tag)) map.set(tag, []);
      map.get(tag)!.push(page);
    }
  }
  return Array.from(map.entries())
    .map(([tag, pages]) => ({ tag, pages }))
    .sort((a, b) => a.tag.localeCompare(b.tag));
}
