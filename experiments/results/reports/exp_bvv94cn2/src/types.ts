export interface Frontmatter {
  title: string;
  date?: string;
  tags?: string[];
  draft?: boolean;
  layout?: string;
  [key: string]: unknown;
}

export interface Page {
  path: string;
  sourcePath: string;
  frontmatter: Frontmatter;
  content: string;
  html: string;
  url: string;
}

export interface SiteConfig {
  sourceDir: string;
  templateDir: string;
  outputDir: string;
  siteTitle: string;
  siteUrl: string;
}

export interface TagIndex {
  tag: string;
  pages: Page[];
}

export interface BuildResult {
  pages: Page[];
  tags: TagIndex[];
  errors: string[];
}
