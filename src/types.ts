export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  content: string;
  template?: string;
  layout?: string;
  data?: Record<string, unknown>;
}
