import http from 'http';
import { FSWatcher } from 'chokidar';

export interface Frontmatter {
  title?: string;
  date?: string;
  tags?: string[];
  template?: string;
  layout?: string | false;
  [key: string]: unknown;
}

export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  sourcePath: string;
  frontmatter: Frontmatter;
  template?: string;
  layout?: string | false;
  cached?: boolean;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  defaultTemplate?: string;
  defaultLayout?: string;
  incremental?: boolean;
  clean?: boolean;
  cacheFile?: string;
}

export interface BuildStats {
  built: number;
  skipped: number;
  timeSavedMs: number;
}

export interface Site {
  pages: Page[];
  outputDir: string;
  stats: BuildStats;
}

export interface ServeOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  port?: number;
  host?: string;
  debounce?: number;
}

export interface DevServer {
  server: http.Server;
  port: number;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  watcher: FSWatcher;
  close(): Promise<void>;
}
