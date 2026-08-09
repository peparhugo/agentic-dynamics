export interface Frontmatter {
  title: string;
  date: Date | null;
  tags: string[];
  draft: boolean;
  layout?: string;
  [key: string]: unknown;
}

export interface Post {
  /** URL slug relative to site root, e.g. "posts/hello-world" */
  slug: string;
  /** Source file path */
  sourcePath: string;
  frontmatter: Frontmatter;
  /** Rendered HTML body */
  html: string;
  /** Raw markdown body */
  markdown: string;
  /** Plain-text excerpt for RSS */
  excerpt: string;
  url: string;
}

export interface SiteConfig {
  sourceDir: string;
  templateDir: string;
  outDir: string;
  baseUrl: string;
  title: string;
  includeDrafts: boolean;
}

export interface BuildResult {
  posts: Post[];
  tagIndex: Map<string, Post[]>;
  pagesWritten: string[];
}
