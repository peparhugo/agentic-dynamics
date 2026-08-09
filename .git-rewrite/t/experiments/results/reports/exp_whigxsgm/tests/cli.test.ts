import { describe, it, expect, beforeAll } from 'vitest';
import path from 'path';
import fs from 'fs';
import os from 'os';
import { run } from '../src/cli';

function tmpDir(prefix: string) {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function copyDir(src: string, dest: string) {
  const entries = fs.readdirSync(src, { withFileTypes: true });
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of entries) {
    const s = path.join(src, entry.name);
    const d = path.join(dest, entry.name);
    if (entry.isDirectory()) copyDir(s, d);
    else fs.copyFileSync(s, d);
  }
}

describe('CLI flags', () => {
  const fxRoot = path.join(__dirname, 'fixtures');
  let work: string;
  let srcDir: string;
  let templatesDir: string;
  let outDir: string;

  beforeAll(() => {
    work = tmpDir('ssg-cli-');
    srcDir = path.join(work, 'content');
    templatesDir = path.join(work, 'templates');
    outDir = path.join(work, 'out');
    copyDir(path.join(fxRoot, 'content'), srcDir);
    copyDir(path.join(fxRoot, 'templates'), templatesDir);
  });

  it('respects src/templates/out flags and site metadata', async () => {
    await run(['node', 'ssg', '--src', srcDir, '--templates', templatesDir, '--out', outDir, '--site-title', 'CLI Site', '--site-url', 'https://cli.example']);
    const indexHtml = fs.readFileSync(path.join(outDir, 'index.html'), 'utf8');
    expect(indexHtml).toContain('CLI Site');
    const rss = fs.readFileSync(path.join(outDir, 'rss.xml'), 'utf8');
    expect(rss).toContain('https://cli.example');
  });
});
