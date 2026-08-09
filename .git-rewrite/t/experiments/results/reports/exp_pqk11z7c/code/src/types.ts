export interface Frontmatter {
  title: string;
  date: Date | null;
  tags: string[];
  draft: boolean;
  layout?: string;
  [key: string]: unknown;
}

export interface Page {
  /** Path of source file relative to the source dir, e.g. "posts/hello.md" */
  sourcePath: string;
  /** Output path relative to the out dir, e.g. "posts/hello/index.html" */
  outputPath: string;
  /** Site-absolute URL, e.g. "/posts/hello/" */
  url: string;
  frontmatter: Frontmatter;
  /** Raw markdown body (without frontmatter) */
  body: string;
  /** Rendered HTML body */
  html: string;
}

export interface SiteConfig {
  sourceDir: string;
  templateDir: string;
  outDir: string;
  baseUrl: string;
  siteTitle: string;
  siteDescription: string;
  includeDrafts: boolean;
}

export interface BuildResult {
  pages: Page[];
  tagPages: string[];
  filesWritten: string[];
}
