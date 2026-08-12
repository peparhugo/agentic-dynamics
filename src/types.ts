export interface Frontmatter {
  title?: string;
  date?: string | Date;
  tags?: string[] | string;
  [key: string]: unknown;
}

export interface Page {
  sourcePath: string;
  slug: string;
  title: string;
  date: string;
  tags: string[];
  content: string;
  html: string;
}
