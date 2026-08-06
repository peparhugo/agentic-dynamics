export interface Post {
  title: string;
  date?: Date;
  tags: string[];
  draft: boolean;
  content: string;
  slug: string;
  raw: string;
}

export interface TemplateContext {
  posts: Post[];
  site: { title: string; description: string; baseUrl: string };
  page?: { title: string; tag?: string };
}

export interface BuilderOptions {
  sourceDir: string;
  templateDir: string;
  outputDir: string;
  baseUrl: string;
  siteTitle: string;
  siteDescription: string;
}

export type LiveReloadMessage = { type: "reload"; path: string };
