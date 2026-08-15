export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  contentHtml: string;
  sourcePath: string;
  outputPath: string;
}

export interface BuildOptions {
  content: string;
  output: string;
}
