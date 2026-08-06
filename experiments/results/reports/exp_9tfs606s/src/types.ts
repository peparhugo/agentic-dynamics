export interface Frontmatter {
  title: string;
  date: Date | null;
  tags: string[];
  draft: boolean;
  layout: string;
  slug?: string;
  description?: string;
  [key: string]: unknown;
}

export interface Page {
  /** Path of the source file relative to the source directory. */
  sourcePath: string;
  /** Output path relative to the output directory, e.g. "posts/hello/index.html". */
  outputPath: string;
  /** Site-absolute URL path, e.g. "/posts/hello/". */
  url: string;
  frontmatter: Frontmatter;
  /** Raw markdown body (frontmatter removed). */
  body: string;
  /** Rendered HTML body. */
  html: string;
  /** Plain-text excerpt derived from the body. */
  excerpt: string;
}

export interface SiteConfig {
  sourceDir: string;
  templateDir: string;
  outputDir: string;
  baseUrl: string;
  title: string;
  description: string;
  includeDrafts: boolean;
  clean: boolean;
}

export interface BuildResult {
  pages: Page[];
  tagPages: string[];
  assets: string[];
  outputFiles: string[];
}

export const DEFAULT_CONFIG: SiteConfig = {
  sourceDir: 'content',
  templateDir: 'templates',
  outputDir: 'dist-site',
  baseUrl: 'http://localhost',
  title: 'My Site',
  description: '',
  includeDrafts: false,
  clean: false,
};
