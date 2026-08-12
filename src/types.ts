export interface Frontmatter {
  title?: string;
  date?: string;
  tags?: string[];
  template?: string;
  layout?: string;
  [key: string]: unknown;
}

export interface Page {
  slug: string;
  link: string;
  outputPath: string;
  filePath: string;
  data: Frontmatter;
  content: string;
  html: string;
  template?: string;
  layout?: string;
}
