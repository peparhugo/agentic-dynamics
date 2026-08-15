import * as fs from 'fs';
import type { Plugin } from './plugin';

export interface SsgConfig {
  plugins?: Plugin[];
}

let tsLoaderRegistered = false;

/**
 * Registers ts-node so plain `require()` can load a raw .ts config file when
 * running outside a TypeScript-aware host (e.g. the compiled CLI). Under a
 * host that already understands .ts files (such as ts-jest during tests),
 * this is a harmless no-op.
 */
function ensureTypeScriptLoader(): void {
  if (tsLoaderRegistered) return;
  tsLoaderRegistered = true;
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    require('ts-node/register');
  } catch {
    // The current runtime may already be able to load .ts files without it.
  }
}

/**
 * Loads plugin configuration from an `ssg.config.ts` (or .js) file at
 * `configPath`. Returns an empty config when the file does not exist, so
 * callers can fall back to their own built-in defaults.
 */
export function loadConfig(configPath: string): SsgConfig {
  if (!fs.existsSync(configPath)) {
    return {};
  }

  if (configPath.endsWith('.ts')) {
    ensureTypeScriptLoader();
  }

  const resolved = require.resolve(configPath);
  delete require.cache[resolved];
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const loaded = require(resolved);
  const config: SsgConfig = loaded?.default ?? loaded;
  return config ?? {};
}
