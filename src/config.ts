import fs from 'fs';
import path from 'path';

export interface SsgConfig {
  plugins?: string[];
}

const CONFIG_FILENAMES = ['ssg.config.ts', 'ssg.config.js'];

/**
 * Load the project configuration from ssg.config.ts (or a compiled
 * ssg.config.js fallback). A raw TypeScript config can only be required when a
 * runtime loader (ts-node/tsx) is active, so unloadable files are skipped.
 */
export function loadConfig(cwd: string): SsgConfig {
  for (const filename of CONFIG_FILENAMES) {
    const file = path.join(cwd, filename);
    if (!fs.existsSync(file)) {
      continue;
    }
    try {
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const loaded = require(file);
      return normalizeConfig(loaded && 'default' in loaded ? loaded.default : loaded);
    } catch {
      // Ignore configs that cannot be loaded at runtime.
    }
  }
  return {};
}

function normalizeConfig(raw: unknown): SsgConfig {
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
    const plugins = (raw as { plugins?: unknown }).plugins;
    if (Array.isArray(plugins)) {
      return { plugins: plugins.filter((p): p is string => typeof p === 'string') };
    }
  }
  return {};
}
