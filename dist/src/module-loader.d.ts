/**
 * Load a TypeScript module by transpiling it to CommonJS in memory and
 * evaluating it. Returns the module's default export (or the module itself
 * when there is no default export).
 *
 * This is used to load `ssg.config.ts` and plugin modules from `./plugins/`
 * without requiring a registered transpiler hook.
 */
export declare function loadTsModule<T>(filePath: string): T;
