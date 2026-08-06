export interface Frontmatter {
  title: string;
  date?: Date;
  tags?: string[];
  draft?: boolean;
  layout?: string;
  [key: string]: unknown;
}

export interface Page {
  path: string;
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

export interface TagMap {
  [tag: string]: Page[];
}
