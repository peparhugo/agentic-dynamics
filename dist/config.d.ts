export interface SsgConfig {
    plugins?: string[];
}
/**
 * Load the project configuration from ssg.config.ts (or a compiled
 * ssg.config.js fallback). A raw TypeScript config can only be required when a
 * runtime loader (ts-node/tsx) is active, so unloadable files are skipped.
 */
export declare function loadConfig(cwd: string): SsgConfig;
