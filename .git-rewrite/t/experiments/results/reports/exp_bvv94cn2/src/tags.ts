import type { Page, TagIndex } from "./types.js";

export function buildTagIndexes(pages: Page[]): TagIndex[] {
  const tagMap = new Map<string, Page[]>();

  for (const page of pages) {
    if (page.frontmatter.draft) continue;
    const tags = page.frontmatter.tags;
    if (!tags || tags.length === 0) continue;

    for (const tag of tags) {
      const existing = tagMap.get(tag) ?? [];
      existing.push(page);
      tagMap.set(tag, existing);
    }
  }

  const indexes: TagIndex[] = [];
  for (const [tag, taggedPages] of tagMap.entries()) {
    taggedPages.sort((a, b) => {
      const da = a.frontmatter.date ?? "";
      const db = b.frontmatter.date ?? "";
      return db.localeCompare(da);
    });
    indexes.push({ tag, pages: taggedPages });
  }

  indexes.sort((a, b) => a.tag.localeCompare(b.tag));
  return indexes;
}
