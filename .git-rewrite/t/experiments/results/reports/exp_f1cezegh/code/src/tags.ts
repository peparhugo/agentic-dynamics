import { Page } from "./types";

export function generateTagIndexes(pages: Page[]): Map<string, Page[]> {
  const byTag = new Map<string, Page[]>();

  for (const page of pages) {
    if (page.meta.draft) continue;
    for (const tag of page.meta.tags) {
      const existing = byTag.get(tag) || [];
      existing.push(page);
      byTag.set(tag, existing);
    }
  }

  return byTag;
}

export function generateTagPageData(
  tag: string,
  tagPages: Page[],
  siteTitle: string
): Record<string, unknown> {
  return {
    title: `Tag: ${tag}`,
    tag,
    pages: tagPages.map((p) => ({
      title: p.meta.title,
      url: p.url,
      date: p.meta.date,
      tags: p.meta.tags,
    })),
    siteTitle,
  };
}
