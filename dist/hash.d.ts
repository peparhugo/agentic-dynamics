/**
 * Computes a stable SHA-256 digest for an in-memory string. Used to build the
 * incremental-build fingerprint for page sources and templates.
 */
export declare function hashString(value: string): string;
/** Computes a SHA-256 digest for the UTF-8 contents of a file. */
export declare function hashFile(filePath: string): string;
