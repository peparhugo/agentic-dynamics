export interface Frontmatter {
  title?: string;
  date?: string;
  tags?: string[];
  [key: string]: unknown;
}

export interface ParsedMarkdown {
  frontmatter: Frontmatter;
  content: string;
  html: string;
}

export interface PageMetadata {
  filename: string;
  title: string;
  date?: string;
  tags: string[];
  url: string;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
}
