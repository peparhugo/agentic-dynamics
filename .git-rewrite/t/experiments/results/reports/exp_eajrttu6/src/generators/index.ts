import path from "path";
import type { Page, TagIndexEntry, SiteConfig } from "../types";

export function buildTagIndex(pages: Page[]): TagIndexEntry[] {
  const tagMap = new Map<string, Page[]>();

  for (const page of pages) {
    const tags = page.frontmatter.tags || [];
    for (const tag of tags) {
      const normalized = tag.trim().toLowerCase();
      if (!tagMap.has(normalized)) {
        tagMap.set(normalized, []);
      }
      tagMap.get(normalized)!.push(page);
    }
  }

  const entries: TagIndexEntry[] = [];
  for (const [tag, taggedPages] of tagMap) {
    entries.push({ tag, pages: taggedPages });
  }

  return entries.sort((a, b) => a.tag.localeCompare(b.tag));
}

export function computePageOutputPath(page: Page): string {
  return path.normalize(page.outputPath);
}

export function resolveAssetPath(
  outputDir: string,
  relativePath: string
): string {
  return path.join(outputDir, relativePath);
}

export { buildRssFeed } from "./rss";
