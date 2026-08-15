export interface Frontmatter {
  title?: string;
  date?: string;
  tags?: string[];
}

export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  sourcePath: string;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
}

export interface BuildResult {
  pages: Page[];
  outputDir: string;
}
