import fs from "node:fs";
import path from "node:path";
import matter from "gray-matter";

export interface FrontmatterInput {
  title?: string;
  date?: string;
  tags?: string | string[];
  draft?: boolean;
}

export function parseFrontmatter(
  filePath: string
): { frontmatter: FrontmatterInput; content: string } | null {
  const raw = fs.readFileSync(filePath, "utf-8");
  const parsed = matter(raw);
  const fm = parsed.data as FrontmatterInput;

  return {
    frontmatter: {
      title: fm.title ?? path.basename(filePath, ".md"),
      date: fm.date ?? new Date().toISOString().split("T")[0],
      tags: normalizeTags(fm.tags),
      draft: fm.draft === true || fm.draft === "true",
    },
    content: parsed.content,
  };
}

function normalizeTags(tags: string | string[] | undefined): string[] {
  if (!tags) return [];
  if (Array.isArray(tags)) return tags.filter(Boolean);
  return tags
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
}
