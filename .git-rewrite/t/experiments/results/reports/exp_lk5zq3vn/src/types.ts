export interface Frontmatter {
  title: string;
  date: Date | null;
  tags: string[];
  draft: boolean;
  layout: string;
  /** any extra frontmatter keys pass through to templates */
  extra: Record<string, unknown>;
}

export interface Page {
  /** path of the source file relative to the source dir, e.g. posts/hello.md */
  sourcePath: string;
  /** output path relative to the out dir, e.g. posts/hello.html */
  outPath: string;
  /** site-absolute URL path, e.g. /posts/hello.html */
  urlPath: string;
  frontmatter: Frontmatter;
  /** rendered HTML body (markdown -> html) */
  html: string;
  /** raw markdown body */
  raw: string;
}

export interface SiteConfig {
  sourceDir: string;
  templateDir: string;
  outDir: string;
  includeDrafts: boolean;
  baseUrl: string;
  siteTitle: string;
  siteDescription: string;
}

export const DEFAULT_CONFIG: SiteConfig = {
  sourceDir: "content",
  templateDir: "templates",
  outDir: "dist-site",
  includeDrafts: false,
  baseUrl: "http://localhost:3000",
  siteTitle: "My Site",
  siteDescription: "",
};
