import fs from 'fs';
import path from 'path';
import { SSGConfig } from './plugin';

const DEFAULT_CONFIG_FILE = 'ssg.config.ts';
const COMPILED_CONFIG_FILE = 'ssg.config.js';

export function findConfigFile(configPath?: string): string | undefined {
  const candidates: string[] = [];
  if (configPath) {
    candidates.push(path.resolve(configPath));
  }
  candidates.push(path.resolve(DEFAULT_CONFIG_FILE));
  candidates.push(path.resolve(COMPILED_CONFIG_FILE));
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return undefined;
}

export function loadConfig(configPath?: string): SSGConfig {
  const file = findConfigFile(configPath);
  if (!file) {
    return {};
  }
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const mod = require(file);
  const config = (mod && mod.default) ?? mod;
  if (config && typeof config === 'object') {
    return config as SSGConfig;
  }
  return {};
}
