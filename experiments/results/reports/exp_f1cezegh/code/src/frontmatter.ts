import matter from "gray-matter";
import { PageMeta } from "./types";

export function parseFrontmatter(raw: string): {
  meta: PageMeta;
  content: string;
} {
  const parsed = matter(raw);
  const data = parsed.data as Record<string, unknown>;

  const tags: string[] = (() => {
    const t = data.tags;
    if (Array.isArray(t)) return t.map(String);
    if (typeof t === "string") return t.split(",").map((s: string) => s.trim()).filter(Boolean);
    return [];
  })();

  const draft = typeof data.draft === "boolean" ? data.draft : false;

  let date: Date | undefined;
  if (data.date) {
    date = new Date(data.date as string);
    if (isNaN(date.getTime())) date = undefined;
  }

  const meta: PageMeta = {
    title: (data.title as string) || "Untitled",
    date,
    tags,
    draft,
  };

  for (const key of Object.keys(data)) {
    if (key !== "title" && key !== "date" && key !== "tags" && key !== "draft") {
      meta[key] = data[key];
    }
  }

  return { meta, content: parsed.content };
}
