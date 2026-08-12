import { Page } from './page';

export interface PluginContext {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
}

export interface Plugin {
  name: string;
  onStart?(context: PluginContext): void;
  beforeBuild?(context: PluginContext): void;
  onFile?(page: Page, context: PluginContext): Page | void;
  afterBuild?(context: PluginContext, pages: Page[]): void;
  onEnd?(context: PluginContext): void;
}

export function isPlugin(value: unknown): value is Plugin {
  if (value === null || typeof value !== 'object') return false;
  const candidate = value as Partial<Plugin>;
  return (
    typeof candidate.name === 'string' &&
    (typeof candidate.onStart === 'function' ||
      typeof candidate.beforeBuild === 'function' ||
      typeof candidate.onFile === 'function' ||
      typeof candidate.afterBuild === 'function' ||
      typeof candidate.onEnd === 'function')
  );
}
