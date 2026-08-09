export interface PageMeta {
  title: string;
  date?: Date;
  tags: string[];
  draft: boolean;
  [key: string]: unknown;
}

export interface Page {
  path: string;
  url: string;
  meta: PageMeta;
  content: string;
  raw: string;
}

export interface SiteConfig {
  sourceDir: string;
  outputDir: string;
  templateDir: string;
  siteTitle: string;
  siteUrl: string;
  siteDescription: string;
  port: number;
}
