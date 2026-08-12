import type { Page, BuildOptions } from './generator';

export interface BuildContext {
  options: Required<Pick<BuildOptions, 'contentDir' | 'outputDir' | 'templatesDir'>>;
  pages: Page[];
  files: string[];
}

export interface Plugin {
  onStart?(context: BuildContext): void;
  beforeBuild?(context: BuildContext): void;
  onFile?(page: Page, context: BuildContext): Page | void;
  afterBuild?(context: BuildContext): void;
  onEnd?(context: BuildContext): void;
}

export interface SSGConfig {
  plugins?: Plugin[];
}

export function loadPlugins(directory = process.cwd()): Plugin[] {
  const filename = require('node:path').join(directory, 'ssg.config.ts');
  try {
    const loaded = require(filename) as SSGConfig | { default?: SSGConfig };
    const config = ('default' in loaded && loaded.default ? loaded.default : loaded) as SSGConfig | Plugin[];
    return Array.isArray(config) ? config : Array.isArray(config.plugins) ? config.plugins : [];
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'MODULE_NOT_FOUND' && !require('node:fs').existsSync(filename)) return [];
    throw error;
  }
}
