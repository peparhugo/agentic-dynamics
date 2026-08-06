import { readFile } from "node:fs/promises";
import { basename, extname } from "node:path";
import matter from "gray-matter";
import type { Frontmatter, Page } from "./types.js";

export async function parseFile(path: string): Promise<Page | null> {
  const raw = await readFile(path, "utf-8");
  const { data, content } = matter(raw);
  const fm = normalizeFm(data);
  if (fm.draft) return null;
  const slug = basename(path, extname(path));
  return { frontmatter: fm, content, html: "", slug, sourcePath: path };
}

function normalizeFm(data: Record<string, unknown>): Frontmatter {
  const fm = data as Frontmatter;
  if (fm.date instanceof Date) {
    fm.date = (fm.date as Date).toISOString().slice(0, 10);
  }
  return fm;
}

export function parseString(md: string): { data: Frontmatter; content: string } {
  const { data, content } = matter(md);
  return { data: normalizeFm(data), content };
}
