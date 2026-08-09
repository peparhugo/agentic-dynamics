export interface Frontmatter {
  title: string;
  date?: string;
  tags?: string[];
  draft?: boolean;
  layout?: string;
}

export interface Page {
  sourcePath: string;
  outputPath: string;
  frontmatter: Frontmatter;
  markdown: string;
  html: string;
  url: string;
}

export interface SiteConfig {
  source: string;
  templates: string;
  output: string;
  baseUrl: string;
  includeDrafts: boolean;
  siteTitle: string;
  siteDescription: string;
}

export interface BuildContext {
  config: SiteConfig;
  pages: Page[];
  tagMap: Map<string, Page[]>;
}
