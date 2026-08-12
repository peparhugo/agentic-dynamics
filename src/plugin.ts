import fs from 'node:fs';
import path from 'node:path';
import type { BuildOptions, Page } from './ssg';

export interface BuildContext {
  options: Required<Pick<BuildOptions, 'contentDir' | 'outputDir' | 'templatesDir'>>;
  pages: Page[];
}

export interface Plugin {
  onStart?(context: BuildContext): void | Promise<void>;
  beforeBuild?(context: BuildContext): void | Promise<void>;
  afterBuild?(context: BuildContext): void | Promise<void>;
  onFile?(page: Page, context: BuildContext): Page | void | Promise<Page | void>;
  onEnd?(context: BuildContext): void | Promise<void>;
}

export type PluginExport = Plugin | (() => Plugin);

export interface SsgConfig {
  plugins?: PluginExport[];
}

function modulePlugins(value: unknown): PluginExport[] {
  if (Array.isArray(value)) return value as PluginExport[];
  if (value && typeof value === 'object' && Array.isArray((value as SsgConfig).plugins)) {
    return (value as SsgConfig).plugins!;
  }
  return [];
}

export function resolvePlugins(exports: unknown): Plugin[] {
  return modulePlugins(exports).map((entry) => typeof entry === 'function' ? entry() : entry);
}

export function loadConfiguredPlugins(configPath = path.resolve('ssg.config.ts')): Plugin[] {
  configPath = path.resolve(configPath);
  if (!fs.existsSync(configPath)) {
    const javascriptConfig = configPath.replace(/\.ts$/, '.js');
    if (!fs.existsSync(javascriptConfig)) return [];
    configPath = javascriptConfig;
  }
  // require is intentional: it works for compiled JavaScript and ts-jest config files.
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const loaded = require(configPath) as { default?: unknown } & Record<string, unknown>;
  return resolvePlugins(loaded.default ?? loaded);
}
