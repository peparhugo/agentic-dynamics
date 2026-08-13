import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';

describe('CLI integration', () => {
  const testDir = path.join(__dirname, '../..', '.test-ssg');
  const contentDir = path.join(testDir, 'content');
  const outputDir = path.join(testDir, 'dist');

  beforeEach(() => {
    if (fs.existsSync(testDir)) {
      fs.rmSync(testDir, { recursive: true });
    }
    fs.mkdirSync(contentDir, { recursive: true });
  });

  afterEach(() => {
    if (fs.existsSync(testDir)) {
      fs.rmSync(testDir, { recursive: true });
    }
  });

  it('should build the site from markdown files', () => {
    const content = `---
title: Test Post
date: 2024-01-15
tags:
  - test
---

# Content

This is a test post.`;

    fs.writeFileSync(path.join(contentDir, 'test.md'), content);

    execSync(
      `npm run build && node dist/cli.js build --content ${contentDir} --output ${outputDir}`,
      { cwd: path.join(__dirname, '../..'), stdio: 'pipe' }
    );

    expect(fs.existsSync(outputDir)).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'test.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);

    const testHtml = fs.readFileSync(path.join(outputDir, 'test.html'), 'utf-8');
    expect(testHtml).toContain('Test Post');
    expect(testHtml).toContain('<h1>Content</h1>');
    expect(testHtml).toContain('This is a test post');
  });

  it('should generate index.html with all pages', () => {
    const post1 = `---
title: First Post
date: 2024-01-15
---

First content`;

    const post2 = `---
title: Second Post
date: 2024-01-10
---

Second content`;

    fs.writeFileSync(path.join(contentDir, 'first.md'), post1);
    fs.writeFileSync(path.join(contentDir, 'second.md'), post2);

    execSync(
      `npm run build && node dist/cli.js build --content ${contentDir} --output ${outputDir}`,
      { cwd: path.join(__dirname, '../..'), stdio: 'pipe' }
    );

    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(indexHtml).toContain('First Post');
    expect(indexHtml).toContain('Second Post');
    expect(indexHtml).toContain('2 pages found');
  });

  it('should use default directories if not specified', () => {
    const defaultContent = `---
title: Default Post
---

Content`;

    if (!fs.existsSync('./content')) {
      fs.mkdirSync('./content', { recursive: true });
    }
    fs.writeFileSync('./content/default.md', defaultContent);

    try {
      execSync('npm run build && node dist/cli.js build', {
        cwd: path.join(__dirname, '../..'),
        stdio: 'pipe',
      });

      expect(fs.existsSync('./dist/default.html')).toBe(true);
      expect(fs.existsSync('./dist/index.html')).toBe(true);
    } finally {
      if (fs.existsSync('./content')) {
        fs.rmSync('./content', { recursive: true });
      }
      if (fs.existsSync('./dist')) {
        fs.rmSync('./dist', { recursive: true });
      }
    }
  });

  it('should handle custom content and output directories', () => {
    const customContent = `---
title: Custom Dir Post
---

Content`;

    fs.writeFileSync(path.join(contentDir, 'custom.md'), customContent);

    execSync(
      `npm run build && node dist/cli.js build --content "${contentDir}" --output "${outputDir}"`,
      { cwd: path.join(__dirname, '../..'), stdio: 'pipe' }
    );

    expect(fs.existsSync(path.join(outputDir, 'custom.html'))).toBe(true);
  });
});
