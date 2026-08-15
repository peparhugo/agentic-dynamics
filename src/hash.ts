import crypto from 'crypto';
import fs from 'fs';

/**
 * Computes a stable SHA-256 digest for an in-memory string. Used to build the
 * incremental-build fingerprint for page sources and templates.
 */
export function hashString(value: string): string {
  return crypto.createHash('sha256').update(value).digest('hex');
}

/** Computes a SHA-256 digest for the UTF-8 contents of a file. */
export function hashFile(filePath: string): string {
  return hashString(fs.readFileSync(filePath, 'utf-8'));
}
