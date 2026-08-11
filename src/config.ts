import * as fs from 'fs';
import * as path from 'path';
import { Plugin } from './plugin';

export interface SsgConfig {
  plugins?: Plugin[];
}

const DEFAULT_CONFIG_SEARCH: string[] = [
  'ssg.config.ts',
  'ssg.config.js',
];

function resolveConfig(cwd: string): string | null {
  for (const name of DEFAULT_CONFIG_SEARCH) {
    const filePath = path.join(cwd, name);
    if (fs.existsSync(filePath)) {
      return filePath;
    }
  }
  return null;
}

export function loadConfig(cwd: string = process.cwd()): SsgConfig {
  const configPath = resolveConfig(cwd);
  if (!configPath) {
    return {};
  }

  try {
    const configModule = require(configPath);
    const config: SsgConfig = configModule.default || configModule || {};
    return config;
  } catch {
    return {};
  }
}
