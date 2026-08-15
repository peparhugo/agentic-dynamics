import * as path from 'path';
import { loadTsModule } from './module-loader';
import { SsgConfig } from './plugin';

const DEFAULT_CONFIG_FILE = 'ssg.config.ts';

/**
 * Load the site configuration from `ssg.config.ts` (relative to the current
 * working directory). Returns an empty config when the file is absent or
 * cannot be parsed.
 */
export async function loadConfig(configPath: string = DEFAULT_CONFIG_FILE): Promise<SsgConfig> {
  try {
    const full = path.resolve(process.cwd(), configPath);
    const config = loadTsModule<SsgConfig>(full);
    return config && typeof config === 'object' ? config : {};
  } catch {
    return {};
  }
}
