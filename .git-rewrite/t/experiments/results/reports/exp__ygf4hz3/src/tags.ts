import { Page, TagIndex } from './types';

export function buildTagIndices(pages: Page[]): TagIndex[] {
  const tagMap = new Map<string, Page[]>();

  for (const page of pages) {
    const tags = page.frontmatter.tags || [];
    for (const tag of tags) {
      if (!tagMap.has(tag)) {
        tagMap.set(tag, []);
      }
      tagMap.get(tag)!.push(page);
    }
  }

  const indices: TagIndex[] = [];
  for (const [tag, tagPages] of tagMap) {
    indices.push({ tag, pages: tagPages });
  }

  return indices;
}
