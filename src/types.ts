export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags?: string[];
  contentHtml: string;
  content: string;
  template?: string;
  layout?: string;
  data?: Record<string, unknown>;
  /** Final rendered HTML. Set by the template plugin; reused by incremental builds. */
  renderedHtml?: string;
}

export interface ParsedMarkdown {
  data: Record<string, unknown>;
  content: string;
}

export interface PageContext {
  [key: string]: unknown;
}
