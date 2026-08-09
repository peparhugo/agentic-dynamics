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
  sourcePath: string;
  outputPath: string;
  url: string;
}

export interface SiteConfig {
  sourceDir: string;
  templateDir: string;
  outputDir: string;
  siteTitle: string;
  siteUrl: string;
  baseUrl: string;
  devServerPort: number;
}

export interface TemplateContext {
  site: {
    title: string;
    url: string;
    baseUrl: string;
  };
  page?: {
    title: string;
    date?: string;
    tags?: string[];
    content: string;
    url: string;
  };
  pages?: Page[];
  tags?: TagIndexEntry[];
  currentTag?: string;
}

export interface TagIndexEntry {
  tag: string;
  pages: Page[];
}
