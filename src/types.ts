import type { Plugin } from './plugin';

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templateDir?: string;
  defaultTemplate?: string;
  defaultLayout?: string;
  configPath?: string;
  plugins?: Plugin[];
}

export interface Frontmatter {
  title?: string;
  date?: string | Date;
  tags?: string[] | string;
  template?: string;
  layout?: string;
  [key: string]: unknown;
}

export interface Page {
  sourcePath: string;
  slug: string;
  title: string;
  date: string;
  tags: string[];
  template?: string;
  layout?: string;
  content: string;
  html: string;
  rendered?: string;
}
