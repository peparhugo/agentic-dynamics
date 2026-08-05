export interface Frontmatter {
  title: string;
  date: Date | null;
  tags: string[];
  draft: boolean;
  layout?: string;
  [key: string]: unknown;
}

export interface Page {
  /** Path of the source file relative to the source dir, e.g. "posts/hello.md" */
  sourcePath: string;
  /** URL path, e.g. "/posts/hello/" */
  url: string;
  /** Output path relative to output dir, e.g. "posts/hello/index.html" */
  outputPath: string;
  frontmatter: Frontmatter;
  /** Rendered HTML body (markdown -> html, code highlighted) */
  html: string;
  /** Raw markdown body */
  body: string;
  excerpt: string;
}

export interface SiteConfig {
  title: string;
  url: string;
  description: string;
}

export interface BuildOptions {
  sourceDir: string;
  templateDir: string;
  outputDir: string;
  site?: Partial<SiteConfig>;
  /** Include pages marked draft: true */
  drafts?: boolean;
  /** Extra script injected into every page (used by dev server for live reload) */
  injectScript?: string;
}

export interface BuildResult {
  pages: Page[];
  tags: Map<string, Page[]>;
  /** All files written, relative to outputDir */
  written: string[];
}
