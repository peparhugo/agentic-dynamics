import { BuildOptions, Frontmatter } from './types';
export declare const CACHE_VERSION = 1;
export declare const CACHE_FILENAME = ".ssg-cache.json";
/**
 * A single page's cached build fingerprint. `sourceHash` covers the markdown
 * source, `templateHash` covers the template/layout/partials that affect the
 * page's rendered output, and the remaining fields let us reconstruct the page
 * (and skip re-parsing/re-rendering) on subsequent incremental builds.
 */
export interface CacheEntry {
    sourceHash: string;
    templateHash: string;
    title: string;
    date?: string;
    tags: string[];
    html: string;
    frontmatter: Frontmatter;
    template?: string;
    layout?: string | false;
}
export interface CacheManifest {
    version: number;
    pages: Record<string, CacheEntry>;
}
export declare function hashContent(content: string): string;
export declare function hashFile(file: string): string | null;
export declare function defaultManifest(): CacheManifest;
export declare function loadManifest(file: string): CacheManifest;
export declare function saveManifest(file: string, manifest: CacheManifest): void;
/**
 * Compute the template fingerprint for a page: the resolved template and
 * layout sources (or their built-in defaults) plus every registered partial.
 * Any change to one of these files changes the fingerprint and invalidates the
 * page's cache entry.
 */
export declare function computeTemplateHash(options: BuildOptions, templateName?: string, layoutName?: string | false): string;
