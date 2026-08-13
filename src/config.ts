import { existsSync } from 'node:fs';
import path from 'node:path';
import type { Plugin } from './plugin';

interface SsgConfig {
  plugins?: Array<Plugin | (() => Plugin)>;
}

export async function loadPlugins(directory = process.cwd()): Promise<Plugin[]> {
  const configPath = path.resolve(directory, 'ssg.config.ts');
  if (!existsSync(configPath)) return [];
  // ts-jest registers TypeScript support during tests; compiled CLI loads JavaScript config modules.
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const loaded = require(configPath) as { default?: SsgConfig } & SsgConfig;
  const config = loaded.default ?? loaded;
  return (config.plugins ?? []).map((plugin) => typeof plugin === 'function' ? plugin() : plugin);
}
