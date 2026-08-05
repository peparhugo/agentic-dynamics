export interface Frontmatter {
  title: string;
  date?: Date;
  tags?: string[];
  draft?: boolean;
  [key: string]: unknown;
}

export interface Page {
  frontmatter: Frontmatter;
  content: string;
  html: string;
  raw: string;
  slug: string;
  sourcePath: string;
  outputPath: string;
}

export interface SSGConfig {
  source: string;
  templates: string;
  output: string;
  siteTitle: string;
  siteUrl: string;
  siteDescription: string;
}

export interface TagData {
  tag: string;
  pages: Page[];
}

export interface TemplateContext {
  site: {
    title: string;
    url: string;
    description: string;
  };
  page?: Page;
  pages: Page[];
  tags: TagData[];
  currentTag?: string;
  taggedPages?: Page[];
}
