import { SsgConfig } from './plugin';
/**
 * Load the site configuration from `ssg.config.ts` (relative to the current
 * working directory). Returns an empty config when the file is absent or
 * cannot be parsed.
 */
export declare function loadConfig(configPath?: string): Promise<SsgConfig>;
