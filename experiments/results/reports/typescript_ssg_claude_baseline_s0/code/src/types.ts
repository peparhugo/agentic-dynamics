export interface PageMeta {
  /** Page title; falls back to a title-cased slug when absent. */
  title: string;
  /** Parsed publication date, or null when absent/invalid. */
  date: Date | null;
  /** Normalized, de-duplicated tag list. */
  tags: string[];
  /** Draft pages are excluded from builds unless --drafts is set. */
  draft: boolean;
  /** Layout name (a template in templates/layouts). */
  layout: string;
  /** Any additional frontmatter keys, passed through to templates. */
  extra: Record<string, unknown>;
}

export interface Page {
  sourcePath: string;
  /** Slug relative to the source root, without extension (posix separators). */
  slug: string;
  /** Site-absolute URL, e.g. "/posts/hello/". */
  url: string;
  /** Output path relative to outDir, e.g. "posts/hello/index.html". */
  outFile: string;
  meta: PageMeta;
  /** Rendered HTML of the markdown body (no layout applied). */
  html: string;
}

export interface SiteConfig {
  title: string;
  baseUrl: string;
  description: string;
}

export interface BuildOptions {
  sourceDir: string;
  templateDir: string;
  outDir: string;
  site?: Partial<SiteConfig>;
  includeDrafts?: boolean;
}

export interface BuildResult {
  pages: Page[];
  tagPages: string[];
  skippedDrafts: number;
  outDir: string;
}
