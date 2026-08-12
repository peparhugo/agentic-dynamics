import fs from 'fs';
import os from 'os';
import path from 'path';
import { build } from '../src/ssg';

function makeTempContentDir(files: Record<string, string>): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-content-'));
  for (const [rel, content] of Object.entries(files)) {
    const filePath = path.join(dir, rel);
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, content, 'utf8');
  }
  return dir;
}

describe('build', () => {
  it('generates an HTML page per markdown file and an index', () => {
    const contentDir = makeTempContentDir({
      'about.md': `---
title: About
date: 2024-01-01
---
About me.`,
      'posts/hello.md': `---
title: Hello
date: 2024-06-01
tags: [demo]
---
Hi there.`,
    });
    const outputDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-out-'));

    const pages = build({ contentDir, outputDir });

    expect(pages).toHaveLength(2);
    expect(fs.existsSync(path.join(outputDir, 'about.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'posts/hello.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);

    const about = fs.readFileSync(path.join(outputDir, 'about.html'), 'utf8');
    expect(about).toContain('<title>About</title>');
    expect(about).toContain('About me.');

    const index = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8');
    expect(index).toContain('about.html');
    expect(index).toContain('posts/hello.html');
    expect(index).toContain('<h2>Hello</h2>');
  });

  it('cleans the output directory before building', () => {
    const contentDir = makeTempContentDir({
      'one.md': '# One',
    });
    const outputDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-out-'));
    fs.writeFileSync(path.join(outputDir, 'stale.txt'), 'old', 'utf8');

    build({ contentDir, outputDir });

    expect(fs.existsSync(path.join(outputDir, 'stale.txt'))).toBe(false);
    expect(fs.existsSync(path.join(outputDir, 'one.html'))).toBe(true);
  });

  it('uses default content and output directories', () => {
    const cwd = process.cwd();
    const sandbox = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-sandbox-'));
    fs.mkdirSync(path.join(sandbox, 'content'));
    fs.writeFileSync(path.join(sandbox, 'content', 'x.md'), '---\ntitle: X\n---\nBody.');

    try {
      process.chdir(sandbox);
      const pages = build();
      expect(pages).toHaveLength(1);
      expect(fs.existsSync(path.join(sandbox, 'dist', 'x.html'))).toBe(true);
      expect(fs.existsSync(path.join(sandbox, 'dist', 'index.html'))).toBe(true);
    } finally {
      process.chdir(cwd);
    }
  });

  it('handles an empty content directory gracefully', () => {
    const contentDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-empty-'));
    const outputDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-out-'));

    const pages = build({ contentDir, outputDir });

    expect(pages).toHaveLength(0);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
  });
});
