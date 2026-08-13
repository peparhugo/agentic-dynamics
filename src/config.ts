import { access } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import type { Plugin } from './plugin.js';

export interface SsgConfig { plugins?: Plugin[]; }

export async function loadPlugins(configPath = path.resolve('ssg.config.ts')): Promise<Plugin[]> {
  try {
    await access(configPath);
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
  const { tsImport } = await import('tsx/esm/api');
  const module = await tsImport(pathToFileURL(configPath).href, import.meta.url);
  const config = (module.default ?? module) as SsgConfig;
  if (!config.plugins) return [];
  if (!Array.isArray(config.plugins)) throw new Error('ssg.config.ts plugins must be an array');
  return config.plugins;
}
