export interface Page {
    slug: string;
    title: string;
    date?: string;
    tags: string[];
    content: string;
    html: string;
    sourcePath: string;
    template?: string;
    layout?: string;
    data?: Record<string, unknown>;
    /** Hash of the raw source content, set by the markdown plugin for incremental builds. */
    sourceHash?: string;
}
export interface BuildOptions {
    contentDir: string;
    outputDir: string;
    templatesDir?: string;
    /** Only rebuild pages whose source or template changed. */
    incremental?: boolean;
    /** Ignore any existing cache and force a full rebuild. */
    clean?: boolean;
    /** Location of the `.ssg-cache.json` manifest (defaults to `<cwd>/.ssg-cache.json`). */
    cacheFile?: string;
}
export interface BuildStats {
    /** Number of pages rendered (includes the site index). */
    built: number;
    /** Number of pages whose cached output was reused unchanged. */
    skipped: number;
    /** Estimated wall-clock time saved by skipping unchanged pages, in ms. */
    timeSavedMs: number;
}
export interface ParsedFrontmatter {
    title?: string;
    date?: string;
    tags?: string[];
    [key: string]: unknown;
}
