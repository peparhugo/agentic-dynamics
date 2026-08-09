export interface Frontmatter {
  title: string;
  date?: string;
  tags?: string[];
  draft?: boolean;
  layout?: string;
  [key: string]: unknown;
}

export interface Page {
  frontmatter: Frontmatter;
  content: string;
  html: string;
  slug: string;
  sourcePath: string;
  outputPath: string;
}

export interface TagIndexEntry {
  tag: string;
  pages: Page[];
}

export interface SiteConfig {
  title: string;
  description: string;
  url: string;
  author?: string;
  language?: string;
  postsPerPage?: number;
}
