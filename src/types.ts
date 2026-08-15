export interface PageMetadata {
  title: string;
  date?: string;
  tags: string[];
  [key: string]: unknown;
}

export interface Page {
  metadata: PageMetadata;
  html: string;
  outputPath: string;
}
