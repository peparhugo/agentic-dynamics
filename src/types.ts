import type { Plugin } from './plugin';

export interface Frontmatter {
  title?: string;
  date?: string | Date;
  tags?: string[] | string;
  template?: string;
  layout?: string;
  [key: string]: unknown;
}

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  url: string;
  html: string;
  data?: Frontmatter;
  template?: string;
  layout?: string;
}

export interface BuildOptions {
  content?: string;
  output?: string;
  templates?: string;
  config?: string | false;
  plugins?: Plugin[];
  incremental?: boolean;
  clean?: boolean;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  durationMs: number;
  timeSavedMs: number;
}
