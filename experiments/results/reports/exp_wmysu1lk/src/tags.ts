import { Post, TemplateData } from "./types";

export function buildTagIndex(posts: Post[]): Map<string, Post[]> {
  const index = new Map<string, Post[]>();
  for (const post of posts) {
    for (const tag of post.tags) {
      const existing = index.get(tag) ?? [];
      existing.push(post);
      index.set(tag, existing);
    }
  }
  for (const [, taggedPosts] of index) {
    taggedPosts.sort((a, b) => b.date.localeCompare(a.date));
  }
  return index;
}

export function tagsTemplateData(
  tagIndex: Map<string, Post[]>
): { name: string; posts: Post[] }[] {
  return Array.from(tagIndex.entries()).map(([name, posts]) => ({
    name,
    posts,
  }));
}
