export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags?: string[];
  contentHtml: string;
  content: string;
}

export interface ParsedMarkdown {
  data: Record<string, unknown>;
  content: string;
}
