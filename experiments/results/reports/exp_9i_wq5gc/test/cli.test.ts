import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { describe, it, expect } from 'vitest';
import { runCli } from '../src/cli';

function tmpdir(prefix: string) {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

describe('CLI flags', () => {
  it('excludes drafts by default, includes with --include-drafts', async () => {
    const src = tmpdir('ssg-src-');
    const tpl = tmpdir('ssg-tpl-');
    const out1 = tmpdir('ssg-out-');
    const out2 = tmpdir('ssg-out-');

    // Source with draft and non-draft
    fs.mkdirSync(src, { recursive: true });
    fs.writeFileSync(path.join(src, 'post1.md'), `---\ntitle: P1\n---\nHello`);
    fs.writeFileSync(path.join(src, 'post2.md'), `---\ntitle: P2\ndraft: true\n---\nDraft`);

    // Minimal layout
    const layoutsDir = path.join(tpl, 'layouts');
    fs.mkdirSync(layoutsDir, { recursive: true });
    fs.writeFileSync(path.join(layoutsDir, 'default.hbs'), `<!doctype html><html><body>{{{body}}}</body></html>`);

    // Build without drafts
    await runCli([
      'build',
      '--src',
      src,
      '--templates',
      tpl,
      '--out',
      out1,
      '--clean',
      'true'
    ]);
    const p1 = path.join(out1, 'post1', 'index.html');
    const p2 = path.join(out1, 'post2', 'index.html');
    expect(fs.existsSync(p1)).toBe(true);
    expect(fs.existsSync(p2)).toBe(false);

    // Build with drafts
    await runCli([
      'build',
      '--src',
      src,
      '--templates',
      tpl,
      '--out',
      out2,
      '--include-drafts',
      'true',
      '--clean',
      'true'
    ]);
    const p1b = path.join(out2, 'post1', 'index.html');
    const p2b = path.join(out2, 'post2', 'index.html');
    expect(fs.existsSync(p1b)).toBe(true);
    expect(fs.existsSync(p2b)).toBe(true);
  });
});
