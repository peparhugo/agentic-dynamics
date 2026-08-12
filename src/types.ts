import type { Plugin } from './plugin';

export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  content: string;
  html: string;
  template?: string;
  layout?: string;
  data?: Record<string, unknown>;
  sourceFile?: string;
}

export interface BuildStats {
  incremental: boolean;
  clean: boolean;
  total: number;
  built: number;
  skipped: number;
  timeSavedMs: number;
  durationMs: number;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templateDir?: string;
  plugins?: Plugin[];
  configFile?: string;
  incremental?: boolean;
  clean?: boolean;
  cacheFile?: string;
  onStats?: (stats: BuildStats) => void;
}
