import crypto from 'node:crypto';

export function hashContent(source: string): string {
  return crypto.createHash('sha256').update(source).digest('hex');
}
