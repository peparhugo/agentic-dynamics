export interface Frontmatter {
  title: string;
  date?: string;
  tags?: string[];
  draft?: boolean;
  template?: string;
  layout?: string;
  [key: string]: unknown;
}

export interface Page {
  path: string;
  url: string;
  frontmatter: Frontmatter;
  content: string;
  html: string;
}

export interface TagIndex {
  tag: string;
  pages: Page[];
}

export interface CLIOptions {
  source: string;
  templates: string;
  output: string;
  port: number;
  drafts: boolean;
}
