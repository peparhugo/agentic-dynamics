import { Page, TagData } from "./types";

export function buildTagData(pages: Page[]): TagData[] {
  const tagMap = new Map<string, Page[]>();

  for (const page of pages) {
    const tags = page.frontmatter.tags ?? [];
    for (const tag of tags) {
      const normalized = tag.toLowerCase().trim();
      if (!tagMap.has(normalized)) {
        tagMap.set(normalized, []);
      }
      tagMap.get(normalized)!.push(page);
    }
  }

  const result: TagData[] = [];
  for (const [tag, taggedPages] of tagMap) {
    taggedPages.sort((a, b) => {
      const da = a.frontmatter.date ?? "";
      const db = b.frontmatter.date ?? "";
      return db.localeCompare(da);
    });
    result.push({ tag, pages: taggedPages });
  }

  result.sort((a, b) => a.tag.localeCompare(b.tag));
  return result;
}
