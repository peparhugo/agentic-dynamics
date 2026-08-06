export interface Frontmatter {
  title: string;
  date?: string;
  tags?: string[];
  draft?: boolean;
  [key: string]: unknown;
}

export interface Page {
  path: string;
  frontmatter: Frontmatter;
  content: string;
  html: string;
  url: string;
  isDraft: boolean;
}

export interface SiteConfig {
  sourceDir: string;
  templateDir: string;
  outputDir: string;
  siteTitle: string;
  siteUrl: string;
  postsPerPage: number;
}

export interface TagInfo {
  name: string;
  pages: Page[];
  count: number;
}
