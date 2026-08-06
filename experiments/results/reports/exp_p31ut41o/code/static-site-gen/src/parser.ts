import matter from "gray-matter";
import { readFile } from "node:fs/promises";
import { ParsedDocument, Frontmatter } from "./types.js";

export function parseFrontmatter(raw: string): ParsedDocument {
  const { data, content } = matter(raw);
  return {
    frontmatter: data as Frontmatter,
    body: content.trim(),
    raw,
  };
}

export async function parseFile(filePath: string): Promise<ParsedDocument> {
  const raw = await readFile(filePath, "utf-8");
  return parseFrontmatter(raw);
}

export function defaultFrontmatter(overrides?: Partial<Frontmatter>): Frontmatter {
  return {
    title: "Untitled",
    draft: false,
    ...overrides,
  };
}
