export interface PageFrontmatter {
  title: string;
  date: string;
  tags: string[];
  template?: string;
  layout?: string;
}

export interface Page extends PageFrontmatter {
  slug: string;
  sourcePath: string;
  outputPath: string;
  html: string;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
}

export interface BuildResult {
  pages: Page[];
  outputDir: string;
}
