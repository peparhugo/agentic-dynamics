export type FrontMatter = {
  title?: string;
  date?: string | Date;
  tags?: string[] | string;
  draft?: boolean;
  slug?: string;
  layout?: string;
};

export type PageMeta = {
  title?: string;
  date?: Date | null;
  tags: string[];
  draft: boolean;
  slug: string;
  layout: string;
  sourcePath: string;
  url: string; // "/foo/bar/"
};

export type Page = PageMeta & {
  bodyHtml: string;
};

export type BuildOptions = {
  srcDir: string;
  templatesDir: string;
  outDir: string;
  includeDrafts?: boolean;
  baseUrl?: string; // for RSS absolute links
  cleanOutDir?: boolean;
  devServerPort?: number; // inject live reload when provided
};

export type SiteData = {
  baseUrl?: string;
  buildTime: string; // ISO
  pages: PageMeta[];
  tags: Record<string, PageMeta[]>;
};
