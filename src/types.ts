export interface PageFrontmatter {
  title?: string;
  date?: string;
  tags?: string[] | string;
  [key: string]: unknown;
}

export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  outputPath: string;
}
