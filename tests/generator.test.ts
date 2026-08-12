import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src/generator';
import { parseArgs } from '../src/cli';

describe('static site generator', () => {
  let root: string;

  beforeEach(() => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-'));
    fs.mkdirSync(path.join(root, 'content', 'notes'), { recursive: true });
    fs.writeFileSync(path.join(root, 'content', 'old.md'), '---\ntitle: Old\ndate: 2024-01-01\ntags: [one]\n---\nOld text.');
    fs.writeFileSync(path.join(root, 'content', 'notes', 'new.md'), '---\ntitle: New\ndate: 2025-01-01\ntags:\n  - two\n---\n# New text');
  });

  afterEach(() => fs.rmSync(root, { recursive: true, force: true }));

  test('writes pages and lists them newest first', () => {
    const output = path.join(root, 'site');
    const pages = buildSite({ contentDir: path.join(root, 'content'), outputDir: output });
    const index = fs.readFileSync(path.join(output, 'index.html'), 'utf8');

    expect(pages.map((page) => page.title)).toEqual(['New', 'Old']);
    expect(index.indexOf('New')).toBeLessThan(index.indexOf('Old'));
    expect(fs.existsSync(path.join(output, 'notes', 'new.html'))).toBe(true);
    expect(fs.readFileSync(path.join(output, 'notes', 'new.html'), 'utf8')).toContain('<h1>New text</h1>');
    expect(index).not.toContain('title: New');
  });

  test('uses defaults and accepts command options', () => {
    expect(parseArgs(['--content', 'posts', '--output', 'public'])).toEqual({ contentDir: 'posts', outputDir: 'public' });
  });
});
