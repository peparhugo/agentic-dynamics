export interface Frontmatter {
  title: string;
  date: Date | null;
  tags: string[];
  draft: boolean;
  layout?: string;
  [key: string]: unknown;
}

export interface Page {
  /** Path of source file relative to source dir, e.g. "posts/hello.md" */
  sourcePath: string;
  /** Output path relative to out dir, e.g. "posts/hello.html" */
  outputPath: string;
  /** Site-absolute URL, e.g. "/posts/hello.html" */
  url: string;
  frontmatter: Frontmatter;
  /** Raw markdown body (without frontmatter) */
  body: string;
  /** Rendered HTML of body */
  html: string;
  /** Plain-text excerpt for feeds/listings */
  excerpt: string;
}

export interface SiteConfig {
  source: string;
  templates: string;
  out: string;
  /** Base URL used for RSS absolute links */
  baseUrl: string;
  title: string;
  description: string;
  /** Include draft pages in the build */
  drafts: boolean;
}

export interface BuildResult {
  pages: Page[];
  tagPages: string[];
  wroteFiles: string[];
}

export const DEFAULT_CONFIG: SiteConfig = {
  source: 'content',
  templates: 'templates',
  out: 'dist-site',
  baseUrl: 'https://example.com',
  title: 'My Site',
  description: 'A static site',
  drafts: false,
};
