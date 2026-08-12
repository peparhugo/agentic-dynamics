export interface Frontmatter {
  title?: unknown;
  date?: unknown;
  tags?: unknown;
  [key: string]: unknown;
}

export interface Page {
  slug: string;
  title: string;
  date: string | null;
  tags: string[];
  contentHtml: string;
  raw: string;
  frontmatter: Frontmatter;
  fileName: string;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
}
