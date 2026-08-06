import type { Frontmatter } from "./frontmatter.js";

export interface TagIndex {
  tag: string;
  posts: Frontmatter[];
}

export function buildTagIndex(postFms: Frontmatter[]): TagIndex[] {
  const map = new Map<string, Frontmatter[]>();
  for (const fm of postFms) {
    if (!fm.tags) continue;
    for (const tag of fm.tags) {
      const list = map.get(tag) ?? [];
      list.push(fm);
      map.set(tag, list);
    }
  }

  const indices: TagIndex[] = [];
  for (const [tag, posts] of map) {
    posts.sort((a, b) => (b.date ?? "").localeCompare(a.date ?? ""));
    indices.push({ tag, posts });
  }
  indices.sort((a, b) => a.tag.localeCompare(b.tag));
  return indices;
}
