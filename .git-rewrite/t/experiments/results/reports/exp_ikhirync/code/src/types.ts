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
}

export interface Site {
  pages: Page[];
  tags: Map<string, Page[]>;
}

export interface BuildOptions {
  source: string;
  templates: string;
  output: string;
}

export interface ServeOptions extends BuildOptions {
  port: number;
}
