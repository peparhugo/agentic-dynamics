export interface Frontmatter {
  title?: string;
  date?: Date | string;
  tags?: string[];
}

export interface Page {
  slug: string;
  title: string;
  date: Date;
  tags: string[];
  html: string;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
}
