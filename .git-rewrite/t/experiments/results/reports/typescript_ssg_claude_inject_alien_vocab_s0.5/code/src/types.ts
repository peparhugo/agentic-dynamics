/** Core shared types for the site generator. */

export interface Frontmatter {
  title: string;
  date: Date | null;
  tags: string[];
  draft: boolean;
  layout?: string;
  /** Any extra user-defined frontmatter keys pass through untouched. */
  [key: string]: unknown;
}

export interface Page {
  /** Path relative to the source dir, e.g. "posts/hello.md". */
  sourcePath: string;
  /** Output path relative to the output dir, e.g. "posts/hello/index.html". */
  outputPath: string;
  /** Site-absolute URL, e.g. "/posts/hello/". */
  url: string;
  frontmatter: Frontmatter;
  /** Raw markdown body (after frontmatter). */
  body: string;
  /** Rendered HTML body. */
  html: string;
  /** First paragraph or frontmatter `description`, for feeds/listings. */
  excerpt: string;
}

export interface SiteConfig {
  sourceDir: string;
  templateDir: string;
  outDir: string;
  baseUrl: string;
  title: string;
  description: string;
  includeDrafts: boolean;
}

export interface BuildResult {
  pages: Page[];
  tagPages: string[];
  filesWritten: string[];
}

export const DEFAULT_CONFIG: SiteConfig = {
  sourceDir: 'content',
  templateDir: 'templates',
  outDir: 'dist-site',
  baseUrl: 'https://example.com',
  title: 'My Site',
  description: '',
  includeDrafts: false,
};
