export interface Frontmatter {
  title: string;
  date?: string;
  tags?: string[];
  draft?: boolean;
  layout?: string;
  [key: string]: unknown;
}

export interface ParsedDocument {
  frontmatter: Frontmatter;
  body: string;
  raw: string;
}

export interface Page {
  frontmatter: Frontmatter;
  content: string;
  html: string;
  url: string;
  sourcePath: string;
  outputPath: string;
  template?: string;
  isPost?: boolean;
}

export interface SiteConfig {
  sourceDir: string;
  templateDir: string;
  outputDir: string;
  siteTitle: string;
  siteUrl: string;
  siteDescription: string;
  postsPerPage: number;
}

export interface TagIndex {
  tag: string;
  pages: Page[];
}

export interface Site {
  pages: Page[];
  posts: Page[];
  pages2: Page[];
  tags: TagIndex[];
  config: SiteConfig;
}

export interface BuildContext {
  markdownFiles: string[];
  templateFiles: string[];
}
