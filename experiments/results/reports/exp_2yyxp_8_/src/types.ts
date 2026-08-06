export interface Frontmatter {
  title: string;
  date?: Date;
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
  raw: string;
}

export interface TagIndex {
  tag: string;
  pages: Page[];
}

export interface GeneratorConfig {
  sourceDir: string;
  templateDir: string;
  outputDir: string;
  siteTitle: string;
  siteUrl: string;
  dev: boolean;
  port: number;
}
