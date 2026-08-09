export interface Frontmatter {
  title: string;
  date: Date | null;
  tags: string[];
  draft: boolean;
  layout: string;
  [key: string]: unknown;
}

export interface Page {
  /** Path of the source file relative to the source dir, e.g. "posts/hello.md" */
  sourcePath: string;
  /** Output path relative to the output dir, e.g. "posts/hello.html" */
  outputPath: string;
  /** Site-absolute URL, e.g. "/posts/hello.html" */
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
  outputDir: string;
  siteTitle: string;
  siteUrl: string;
  siteDescription: string;
  includeDrafts: boolean;
}

export interface SiteContext {
  title: string;
  url: string;
  description: string;
  pages: Page[];
  tags: Record<string, Page[]>;
}
