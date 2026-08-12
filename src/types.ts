export interface Frontmatter {
  title?: string;
  date?: string;
  tags?: string[];
}

export interface Page {
  slug: string;
  link: string;
  outputPath: string;
  filePath: string;
  data: Frontmatter;
  content: string;
  html: string;
}
