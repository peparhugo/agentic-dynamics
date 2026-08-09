export interface Frontmatter {
  title?: string;
  date?: string;
  tags?: string[];
  draft?: boolean;
  [key: string]: unknown;
}

export interface Page {
  path: string;
  sourcePath: string;
  frontmatter: Frontmatter;
  content: string;
  html: string;
}

export interface SiteConfig {
  siteName: string;
  siteUrl: string;
  author?: string;
}

export interface GeneratorOptions {
  sourceDir: string;
  templateDir: string;
  outputDir: string;
  config: SiteConfig;
}
