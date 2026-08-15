import fs from 'fs';
import path from 'path';
import os from 'os';
import { generate } from './generator';

describe('generator', () => {
  let tempDir: string;
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-test-'));
    contentDir = path.join(tempDir, 'content');
    outputDir = path.join(tempDir, 'dist');

    fs.mkdirSync(contentDir, { recursive: true });
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('generates HTML files from markdown', async () => {
    const content = `---
title: Test Page
---
# Hello

This is a test page.`;

    fs.writeFileSync(path.join(contentDir, 'test.md'), content);

    await generate({ contentDir, outputDir });

    const outputFile = path.join(outputDir, 'test.html');
    expect(fs.existsSync(outputFile)).toBe(true);

    const html = fs.readFileSync(outputFile, 'utf-8');
    expect(html).toContain('<title>Test Page</title>');
    expect(html).toContain('<h1>Hello</h1>');
    expect(html).toContain('This is a test page');
  });

  it('generates index.html with all pages', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'page1.md'),
      `---
title: Page One
date: 2024-01-15
---
Content 1`
    );
    fs.writeFileSync(
      path.join(contentDir, 'page2.md'),
      `---
title: Page Two
date: 2024-01-10
---
Content 2`
    );

    await generate({ contentDir, outputDir });

    const indexFile = path.join(outputDir, 'index.html');
    expect(fs.existsSync(indexFile)).toBe(true);

    const html = fs.readFileSync(indexFile, 'utf-8');
    expect(html).toContain('Page One');
    expect(html).toContain('Page Two');
    expect(html).toContain('href="page1.html"');
    expect(html).toContain('href="page2.html"');
  });

  it('sorts pages by date descending in index', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'old.md'),
      `---
title: Old Post
date: 2024-01-01
---
Old`
    );
    fs.writeFileSync(
      path.join(contentDir, 'new.md'),
      `---
title: New Post
date: 2024-01-31
---
New`
    );

    await generate({ contentDir, outputDir });

    const html = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    const newPos = html.indexOf('New Post');
    const oldPos = html.indexOf('Old Post');
    expect(newPos).toBeLessThan(oldPos);
  });

  it('includes tags in generated pages', async () => {
    const content = `---
title: Tagged Page
tags: typescript, testing
---
Content`;

    fs.writeFileSync(path.join(contentDir, 'tagged.md'), content);

    await generate({ contentDir, outputDir });

    const html = fs.readFileSync(path.join(outputDir, 'tagged.html'), 'utf-8');
    expect(html).toContain('typescript');
    expect(html).toContain('testing');
    expect(html).toContain('class="tag"');
  });

  it('includes date in generated pages', async () => {
    const content = `---
title: Dated Page
date: 2024-01-15
---
Content`;

    fs.writeFileSync(path.join(contentDir, 'dated.md'), content);

    await generate({ contentDir, outputDir });

    const html = fs.readFileSync(path.join(outputDir, 'dated.html'), 'utf-8');
    expect(html).toContain('2024-01-15');
    expect(html).toContain('class="date"');
  });

  it('escapes HTML in titles', async () => {
    const content = `---
title: <script>alert('xss')</script>
---
Content`;

    fs.writeFileSync(path.join(contentDir, 'xss.md'), content);

    await generate({ contentDir, outputDir });

    const html = fs.readFileSync(path.join(outputDir, 'xss.html'), 'utf-8');
    expect(html).toContain('&lt;script&gt;');
    expect(html).not.toContain('<script>alert');
  });

  it('creates output directory if it does not exist', async () => {
    const nonExistentOutput = path.join(tempDir, 'new', 'dist');
    expect(fs.existsSync(nonExistentOutput)).toBe(false);

    fs.writeFileSync(path.join(contentDir, 'test.md'), `---
title: Test
---
Content`);

    await generate({ contentDir, outputDir: nonExistentOutput });

    expect(fs.existsSync(nonExistentOutput)).toBe(true);
    expect(fs.existsSync(path.join(nonExistentOutput, 'test.html'))).toBe(true);
  });

  it('throws error if content directory does not exist', async () => {
    const nonExistent = path.join(tempDir, 'nonexistent');

    await expect(
      generate({ contentDir: nonExistent, outputDir })
    ).rejects.toThrow('Content directory not found');
  });

  it('throws error if no markdown files found', async () => {
    await expect(
      generate({ contentDir, outputDir })
    ).rejects.toThrow('No markdown files found');
  });

  it('includes home link in generated pages', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'page.md'),
      `---
title: Test
---
Content`
    );

    await generate({ contentDir, outputDir });

    const html = fs.readFileSync(path.join(outputDir, 'page.html'), 'utf-8');
    expect(html).toContain('href="index.html"');
    expect(html).toContain('Home');
  });

  it('handles pages without title', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'notitle.md'),
      `# Heading

Content without frontmatter title`
    );

    await generate({ contentDir, outputDir });

    const html = fs.readFileSync(path.join(outputDir, 'notitle.html'), 'utf-8');
    expect(html).toContain('notitle');
    expect(html).toContain('<h1>Heading</h1>');
  });

  it('handles special characters in filenames', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'my-special-page.md'),
      `---
title: Special
---
Content`
    );

    await generate({ contentDir, outputDir });

    expect(fs.existsSync(path.join(outputDir, 'my-special-page.html'))).toBe(true);
  });

  it('includes page count in console output', async () => {
    fs.writeFileSync(path.join(contentDir, 'page1.md'), `---
title: One
---
Content`);
    fs.writeFileSync(path.join(contentDir, 'page2.md'), `---
title: Two
---
Content`);

    const logSpy = jest.spyOn(console, 'log').mockImplementation();

    await generate({ contentDir, outputDir });

    expect(logSpy).toHaveBeenCalledWith(expect.stringContaining('2 page(s)'));
    logSpy.mockRestore();
  });
});
