export interface Frontmatter {
  title: string;
  date?: string;
  tags?: string[];
  template?: string;
  layout?: string;
}

export interface Page {
  frontmatter: Frontmatter;
  content: string;
  slug: string;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
}
