import { access } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import type { Plugin } from './plugin.js';

export interface SsgConfig {
  plugins?: Plugin[];
}

export async function loadPlugins(configPath = 'ssg.config.ts'): Promise<Plugin[]> {
  try {
    await access(configPath);
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }

  const config = await import(pathToFileURL(resolve(configPath)).href) as SsgConfig & { default?: SsgConfig };
  return config.default?.plugins ?? config.plugins ?? [];
}
