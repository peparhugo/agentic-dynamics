export interface Frontmatter {
  title: string;
  date?: string;
  tags: string[];
  template?: string;
  layout?: string;
}

export interface Page {
  sourcePath: string;
  outputPath: string;
  slug: string;
  frontmatter: Frontmatter;
  html: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
}
