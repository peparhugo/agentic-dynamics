import yaml from "js-yaml";
import type { Frontmatter } from "./types.js";

export interface ParsedMarkdown {
  frontmatter: Frontmatter;
  body: string;
}

function normalizeDate(v: unknown): string | undefined {
  if (v instanceof Date) {
    return v.toISOString().split("T")[0];
  }
  if (typeof v === "string") return v;
  return undefined;
}

export function parseFrontmatter(raw: string): ParsedMarkdown {
  const trimmed = raw.trimStart();
  if (!trimmed.startsWith("---")) {
    return { frontmatter: { title: "Untitled" }, body: raw };
  }

  const afterFirst = trimmed.slice(3);
  const endIdx = afterFirst.indexOf("\n---");

  if (endIdx === -1) {
    const endIdxSameLine = afterFirst.indexOf("---");
    if (endIdxSameLine !== -1) {
      const body = afterFirst.slice(endIdxSameLine + 3).trimStart();
      return { frontmatter: { title: "Untitled" }, body };
    }
    return { frontmatter: { title: "Untitled" }, body: raw };
  }

  const yamlBlock = afterFirst.slice(0, endIdx);
  const afterEnd = afterFirst.slice(endIdx + 4);
  const body = afterEnd.startsWith("\n") ? afterEnd.slice(1) : afterEnd;

  let frontmatter: Frontmatter;
  try {
    const parsed = yaml.load(yamlBlock);
    frontmatter = (typeof parsed === "object" && parsed !== null ? parsed : {}) as Frontmatter;
  } catch {
    frontmatter = {} as Frontmatter;
  }

  if (!frontmatter.title) {
    frontmatter.title = "Untitled";
  }

  frontmatter.date = normalizeDate(frontmatter.date);

  if (frontmatter.tags && !Array.isArray(frontmatter.tags)) {
    frontmatter.tags = [String(frontmatter.tags)];
  }
  if (Array.isArray(frontmatter.tags)) {
    frontmatter.tags = frontmatter.tags.map(t => String(t).trim().toLowerCase()).filter(Boolean);
  }

  return { frontmatter, body };
}
