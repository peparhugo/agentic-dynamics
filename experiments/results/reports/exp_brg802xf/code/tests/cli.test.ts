import { describe, it, expect } from 'vitest';
import path from 'node:path';
import { parseCliArgs } from '../src/cli';

describe('CLI flags', () => {
  it('applies defaults', () => {
    const opts = parseCliArgs(['node', 'cli']);
    // paths resolved relative to cwd
    expect(path.isAbsolute(opts.src)).toBe(true);
    expect(opts.drafts).toBe(false);
    expect(opts.watch).toBe(false);
    expect(opts.port).toBe(5173);
  });

  it('parses custom flags', () => {
    const opts = parseCliArgs(['node', 'cli', '--src', 'a', '--templates', 'b', '--out', 'c', '--drafts', '--site-url', 'https://x', '--watch', '--port', '1234']);
    expect(opts.drafts).toBe(true);
    expect(opts.watch).toBe(true);
    expect(opts.port).toBe(1234);
    expect(opts.siteUrl).toBe('https://x');
  });
});
