import path from 'path';

export interface Page {
  title: string;
  date: string;
  tags: string[];
  content: string;
  slug: string;
  layout?: string;
  template?: string;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
}

export interface Plugin {
  name: string;
  onStart?(): void;
  beforeBuild?(options: BuildOptions): void;
  afterBuild?(options: BuildOptions): void;
  onFile?(page: Page): Page;
  onEnd?(): void;
}

export function loadPluginsFromConfig(): Plugin[] {
  try {
    const configPath = path.join(process.cwd(), 'ssg.config');
    const config = require(configPath);
    const plugins = config?.default?.plugins || config?.plugins || [];
    if (Array.isArray(plugins)) return plugins;
    return [];
  } catch {
    return [];
  }
}
