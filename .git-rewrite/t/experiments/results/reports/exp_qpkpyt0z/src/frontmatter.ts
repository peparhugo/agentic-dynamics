import matter from "gray-matter";
import { readFile } from "node:fs/promises";
import { basename } from "node:path";
import type { Frontmatter } from "./types.js";

export function parseFrontmatter(raw: string): {
  data: Frontmatter;
  content: string;
} {
  const { data, content } = matter(raw);
  return {
    data: data as Frontmatter,
    content,
  };
}

export async function readAndParse(filePath: string): Promise<{
  data: Frontmatter;
  content: string;
  slug: string;
}> {
  const raw = await readFile(filePath, "utf-8");
  const { data, content } = parseFrontmatter(raw);
  const slug = basename(filePath, ".md");
  return { data, content, slug };
}

export function isDraft(data: Frontmatter): boolean {
  return data.draft === true;
}

export function isPublishable(data: Frontmatter): boolean {
  return !isDraft(data);
}

export function hasTitle(data: Frontmatter): boolean {
  return typeof data.title === "string" && data.title.trim().length > 0;
}

export function parseTags(data: Frontmatter): string[] {
  const raw = data.tags;
  if (!raw) return [];
  if (Array.isArray(raw)) {
    return (raw as unknown[]).filter((t): t is string => typeof t === "string").map((t) => t.trim().toLowerCase());
  }
  if (typeof raw === "string") return raw.split(",").map((t) => t.trim().toLowerCase()).filter((t) => t.length > 0);
  return [];
}

export function parseDate(data: Frontmatter): Date | null {
  if (!data.date) return null;
  const d = new Date(data.date);
  return isNaN(d.getTime()) ? null : d;
}

export function sortByDate<T extends { frontmatter: Frontmatter }>(items: T[], desc = true): T[] {
  return [...items].sort((a, b) => {
    const da = parseDate(a.frontmatter)?.getTime() ?? 0;
    const db = parseDate(b.frontmatter)?.getTime() ?? 0;
    return desc ? db - da : da - db;
  });
}
