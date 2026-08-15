import crypto from 'crypto';

/** Content hash used throughout the incremental-build cache to detect changed sources/templates. */
export function hashString(input: string): string {
  return crypto.createHash('sha256').update(input).digest('hex');
}
