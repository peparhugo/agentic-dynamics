import { build } from '../src/build';
import fs from 'fs';
import path from 'path';

const testBase = path.join(__dirname, 'integration');
const contentDir = path.join(testBase, 'content');
const outputDir = path.join(testBase, 'dist');

beforeEach(() => {
  if (fs.existsSync(testBase)) {
    fs.rmSync(testBase, { recursive: true, force: true });
  }
  fs.mkdirSync(contentDir, { recursive: true });
});

afterEach(() => {
  if (fs.existsSync(testBase)) {
    fs.rmSync(testBase, { recursive: true, force: true });
  }
});

describe('build', () => {
  it('generates HTML files for each markdown page', () => {
    fs.writeFileSync(
      path.join(contentDir, 'hello.md'),
      `---
title: Hello World
date: 2024-01-15
tags:
  - greeting
---
# Hello

This is a test.`,
      'utf-8',
    );

    build({ contentDir, outputDir });

    const helloPath = path.join(outputDir, 'hello.html');
    expect(fs.existsSync(helloPath)).toBe(true);

    const html = fs.readFileSync(helloPath, 'utf-8');
    expect(html).toContain('<title>Hello World</title>');
    expect(html).toContain('<h1>Hello</h1>');
    expect(html).toContain('This is a test.');
  });

  it('generates an index.html with links to all pages', () => {
    fs.writeFileSync(
      path.join(contentDir, 'alpha.md'),
      `---
title: Alpha
---
Alpha content`,
    );
    fs.writeFileSync(
      path.join(contentDir, 'beta.md'),
      `---
title: Beta
---
Beta content`,
    );

    build({ contentDir, outputDir });

    const indexPath = path.join(outputDir, 'index.html');
    expect(fs.existsSync(indexPath)).toBe(true);

    const indexHtml = fs.readFileSync(indexPath, 'utf-8');
    expect(indexHtml).toContain('<a href="alpha.html">Alpha</a>');
    expect(indexHtml).toContain('<a href="beta.html">Beta</a>');
  });

  it('creates output directory if it does not exist', () => {
    fs.writeFileSync(
      path.join(contentDir, 'page.md'),
      `---
title: Page
---
Content`,
    );

    expect(fs.existsSync(outputDir)).toBe(false);
    build({ contentDir, outputDir });
    expect(fs.existsSync(outputDir)).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'page.html'))).toBe(true);
  });

  it('throws if content directory does not exist', () => {
    expect(() =>
      build({ contentDir: '/nonexistent/content', outputDir }),
    ).toThrow('Content directory not found');
  });

  it('handles empty content directory', () => {
    build({ contentDir, outputDir });

    const indexPath = path.join(outputDir, 'index.html');
    expect(fs.existsSync(indexPath)).toBe(true);
    const html = fs.readFileSync(indexPath, 'utf-8');
    expect(html).toContain('All Pages');
  });
});
