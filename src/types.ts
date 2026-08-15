export interface Frontmatter {
  title?: string;
  date?: Date | string;
  tags?: string[];
  template?: string;
  layout?: string;
}

export interface Page {
  slug: string;
  title: string;
  date: Date;
  tags: string[];
  html: string;
  template?: string;
  layout?: string;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
}
