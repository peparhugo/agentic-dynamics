export interface Frontmatter {
  title: string;
  date?: string;
  tags?: string[];
  draft?: boolean;
  [key: string]: unknown;
}

export interface Page {
  path: string;
  url: string;
  frontmatter: Frontmatter;
  content: string;
  html: string;
  isPost: boolean;
}

export interface SiteConfig {
  title: string;
  description: string;
  baseUrl: string;
  language: string;
}

export interface BuildContext {
  pages: Page[];
  tags: Map<string, Page[]>;
  config: SiteConfig;
  startTime: Date;
}
