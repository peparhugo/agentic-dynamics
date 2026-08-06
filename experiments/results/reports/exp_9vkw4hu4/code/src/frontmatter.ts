import matter from "gray-matter";

export interface Frontmatter {
  title: string;
  date?: string;
  tags?: string[];
  draft?: boolean;
  layout?: string;
  [key: string]: unknown;
}

export interface ParsedMarkdown {
  frontmatter: Frontmatter;
  content: string;
  raw: string;
}

export function parseFrontmatter(raw: string): ParsedMarkdown {
  const { data, content } = matter(raw);
  const frontmatter = normalizeFrontmatter(data);
  return { frontmatter, content, raw };
}

function normalizeFrontmatter(data: Record<string, unknown>): Frontmatter {
  const fm: Frontmatter = {
    title: typeof data.title === "string" ? data.title : "Untitled",
  };

  if (typeof data.date === "string" || data.date instanceof Date) {
    fm.date = new Date(data.date as string | Date).toISOString();
  }

  if (Array.isArray(data.tags)) {
    fm.tags = data.tags.map((t) => String(t));
  } else if (typeof data.tags === "string") {
    fm.tags = data.tags.split(",").map((t) => t.trim());
  }

  if (data.draft !== undefined) {
    fm.draft = Boolean(data.draft);
  }

  if (typeof data.layout === "string") {
    fm.layout = data.layout;
  }

  for (const [key, value] of Object.entries(data)) {
    if (!["title", "date", "tags", "draft", "layout"].includes(key)) {
      fm[key] = value;
    }
  }

  return fm;
}
