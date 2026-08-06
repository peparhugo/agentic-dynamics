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
}

export interface SiteConfig {
  src: string;
  tmpl: string;
  out: string;
  port: number;
  baseUrl: string;
  title: string;
  description: string;
}
