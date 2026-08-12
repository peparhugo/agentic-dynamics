export interface PageData {
  title?: string;
  date?: string;
  tags?: string[];
  [key: string]: unknown;
}

export interface Page {
  slug: string;
  sourcePath: string;
  data: PageData;
  body: string;
  html: string;
  outputFile: string;
}
