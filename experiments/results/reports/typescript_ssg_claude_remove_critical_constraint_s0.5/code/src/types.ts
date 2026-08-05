export interface Frontmatter {
  title: string;
  date: Date | null;
  tags: string[];
  draft: boolean;
  layout: string;
  description: string;
  /** Optional explicit slug override for the output path segment. */
  slug?: string;
  /** Any extra frontmatter keys are passed through to templates. */
  [key: string]: unknown;
}

export interface Page {
  /** Path of the source file relative to the source dir, e.g. "posts/hello.md". */
  sourcePath: string;
  /** Output path relative to the out dir, e.g. "posts/hello/index.html". */
  outputPath: string;
  /** Site-absolute URL, e.g. "/posts/hello/". */
  url: string;
  frontmatter: Frontmatter;
  /** Raw markdown body (frontmatter stripped). */
  body: string;
  /** Rendered HTML of the body. */
  html: string;
  /** Plain-text excerpt derived from description or the first paragraph. */
  excerpt: string;
}

export interface SiteConfig {
  sourceDir: string;
  templateDir: string;
  outDir: string;
  title: string;
  description: string;
  baseUrl: string;
  includeDrafts: boolean;
  clean: boolean;
  port: number;
}

export interface BuildResult {
  pages: Page[];
  tags: Record<string, Page[]>;
  /** Output files written, relative to outDir. */
  written: string[];
}

export const DEFAULT_CONFIG: SiteConfig = {
  sourceDir: 'content',
  templateDir: 'templates',
  outDir: 'dist-site',
  title: 'My Site',
  description: '',
  baseUrl: 'http://localhost:3000',
  includeDrafts: false,
  clean: false,
  port: 3000,
};
