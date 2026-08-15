import type { Frontmatter } from './frontmatter';

export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  contentHtml: string;
  sourcePath: string;
  outputPath: string;
  template?: string;
  layout?: string;
  data: Frontmatter;
}

export interface BuildOptions {
  content: string;
  output: string;
  templates?: string;
}
