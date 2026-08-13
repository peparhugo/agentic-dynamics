export interface PageFrontmatter {
  title: string;
  date: string;
  tags: string[];
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
}

export interface BuildResult {
  pages: Page[];
  outputDir: string;
}
