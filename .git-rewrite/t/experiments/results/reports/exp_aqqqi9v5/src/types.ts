export interface Frontmatter {
  title: string;
  date?: string;
  tags?: string[];
  draft?: boolean;
  [key: string]: unknown;
}

export interface Page {
  frontmatter: Frontmatter;
  content: string;
  html: string;
  slug: string;
  sourcePath: string;
  outputPath: string;
  isDraft: boolean;
}

export interface TagIndex {
  tag: string;
  pages: Page[];
}

export interface BuildContext {
  pages: Page[];
  tags: Map<string, Page[]>;
  config: SiteConfig;
}

export interface SiteConfig {
  title: string;
  description: string;
  baseUrl: string;
  sourceDir: string;
  templateDir: string;
  outputDir: string;
}
