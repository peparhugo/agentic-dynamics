export interface Page {
  slug: string;
  title: string;
  date: string | null;
  tags: string[];
  html: string;
  sourcePath: string;
  outputPath: string;
  template: string;
  layout: string;
}
