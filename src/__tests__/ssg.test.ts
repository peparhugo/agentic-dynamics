import * as fs from 'fs';
import * as path from 'path';
import { build } from '../ssg.js';

describe('Static Site Generator', () => {
  let testContentDir: string;
  let testOutputDir: string;

  beforeEach(() => {
    testContentDir = path.join('/tmp', `test-content-${Date.now()}`);
    testOutputDir = path.join('/tmp', `test-output-${Date.now()}`);
    fs.mkdirSync(testContentDir, { recursive: true });
  });

  afterEach(() => {
    if (fs.existsSync(testContentDir)) {
      fs.rmSync(testContentDir, { recursive: true });
    }
    if (fs.existsSync(testOutputDir)) {
      fs.rmSync(testOutputDir, { recursive: true });
    }
  });

  it('should create output directory if it does not exist', () => {
    fs.writeFileSync(path.join(testContentDir, 'test.md'), '# Test\nContent');
    build(testContentDir, testOutputDir);
    expect(fs.existsSync(testOutputDir)).toBe(true);
  });

  it('should generate index.html when no markdown files exist', () => {
    build(testContentDir, testOutputDir);
    const indexPath = path.join(testOutputDir, 'index.html');
    expect(fs.existsSync(indexPath)).toBe(true);
    const content = fs.readFileSync(indexPath, 'utf-8');
    expect(content).toContain('No pages found');
  });

  it('should parse markdown and create HTML files', () => {
    const mdContent = `---
title: Test Post
---
# Test Post
This is test content.`;

    fs.writeFileSync(path.join(testContentDir, 'test.md'), mdContent);
    build(testContentDir, testOutputDir);

    const htmlPath = path.join(testOutputDir, 'test.html');
    expect(fs.existsSync(htmlPath)).toBe(true);

    const html = fs.readFileSync(htmlPath, 'utf-8');
    expect(html).toContain('Test Post');
    expect(html).toContain('This is test content');
  });

  it('should generate index.html with links to all pages', () => {
    const post1 = `---
title: First Post
---
Content 1`;

    const post2 = `---
title: Second Post
date: 2024-01-15
---
Content 2`;

    fs.writeFileSync(path.join(testContentDir, 'first.md'), post1);
    fs.writeFileSync(path.join(testContentDir, 'second.md'), post2);
    build(testContentDir, testOutputDir);

    const indexPath = path.join(testOutputDir, 'index.html');
    const index = fs.readFileSync(indexPath, 'utf-8');

    expect(index).toContain('first.html');
    expect(index).toContain('second.html');
    expect(index).toContain('First Post');
    expect(index).toContain('Second Post');
    expect(index).toContain('2024-01-15');
  });

  it('should include back link in page HTML', () => {
    const mdContent = `---
title: Test
---
Content`;

    fs.writeFileSync(path.join(testContentDir, 'test.md'), mdContent);
    build(testContentDir, testOutputDir);

    const html = fs.readFileSync(path.join(testOutputDir, 'test.html'), 'utf-8');
    expect(html).toContain('← Home');
    expect(html).toContain('/index.html');
  });

  it('should handle markdown with code blocks', () => {
    const mdContent = `---
title: Code Post
---
\`\`\`javascript
console.log('hello');
\`\`\``;

    fs.writeFileSync(path.join(testContentDir, 'code.md'), mdContent);
    build(testContentDir, testOutputDir);

    const html = fs.readFileSync(path.join(testOutputDir, 'code.html'), 'utf-8');
    expect(html).toContain('console.log');
  });

  it('should handle markdown with lists', () => {
    const mdContent = `---
title: Lists
---
- Item 1
- Item 2
- Item 3`;

    fs.writeFileSync(path.join(testContentDir, 'lists.md'), mdContent);
    build(testContentDir, testOutputDir);

    const html = fs.readFileSync(path.join(testOutputDir, 'lists.html'), 'utf-8');
    expect(html).toContain('Item 1');
    expect(html).toContain('Item 2');
    expect(html).toContain('Item 3');
  });

  it('should include date in page HTML if present', () => {
    const mdContent = `---
title: Dated Post
date: 2024-01-15
---
Content`;

    fs.writeFileSync(path.join(testContentDir, 'dated.md'), mdContent);
    build(testContentDir, testOutputDir);

    const html = fs.readFileSync(path.join(testOutputDir, 'dated.html'), 'utf-8');
    expect(html).toContain('2024-01-15');
    expect(html).toContain('class="date"');
  });

  it('should include tags in page HTML if present', () => {
    const mdContent = `---
title: Tagged Post
tags: [javascript, typescript, web]
---
Content`;

    fs.writeFileSync(path.join(testContentDir, 'tagged.md'), mdContent);
    build(testContentDir, testOutputDir);

    const html = fs.readFileSync(path.join(testOutputDir, 'tagged.html'), 'utf-8');
    expect(html).toContain('javascript');
    expect(html).toContain('typescript');
    expect(html).toContain('web');
    expect(html).toContain('class="tags"');
  });

  it('should generate proper HTML structure with charset and viewport', () => {
    const mdContent = `---
title: Test
---
Content`;

    fs.writeFileSync(path.join(testContentDir, 'test.md'), mdContent);
    build(testContentDir, testOutputDir);

    const html = fs.readFileSync(path.join(testOutputDir, 'test.html'), 'utf-8');
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('charset="UTF-8"');
    expect(html).toContain('viewport');
  });

  it('should slugify filenames correctly', () => {
    const mdContent = `---
title: Test
---
Content`;

    fs.writeFileSync(path.join(testContentDir, 'My Test Page.md'), mdContent);
    build(testContentDir, testOutputDir);

    const htmlPath = path.join(testOutputDir, 'my-test-page.html');
    expect(fs.existsSync(htmlPath)).toBe(true);
  });

  it('should handle multiple markdown files in sequence', () => {
    for (let i = 1; i <= 3; i++) {
      const mdContent = `---
title: Post ${i}
date: 2024-01-${String(i).padStart(2, '0')}
---
Content for post ${i}`;

      fs.writeFileSync(path.join(testContentDir, `post${i}.md`), mdContent);
    }

    build(testContentDir, testOutputDir);

    for (let i = 1; i <= 3; i++) {
      const htmlPath = path.join(testOutputDir, `post${i}.html`);
      expect(fs.existsSync(htmlPath)).toBe(true);
    }

    const indexPath = path.join(testOutputDir, 'index.html');
    const index = fs.readFileSync(indexPath, 'utf-8');
    expect(index).toContain('Post 1');
    expect(index).toContain('Post 2');
    expect(index).toContain('Post 3');
  });

  it('should handle content directory that does not exist', () => {
    const nonExistentDir = path.join('/tmp', `non-existent-${Date.now()}`);
    expect(() => build(nonExistentDir, testOutputDir)).not.toThrow();
    expect(fs.existsSync(testOutputDir)).toBe(true);
  });

  it('should use filename as title if not provided in frontmatter', () => {
    const mdContent = `---
---
Content without title`;

    fs.writeFileSync(path.join(testContentDir, 'my-page.md'), mdContent);
    build(testContentDir, testOutputDir);

    const html = fs.readFileSync(path.join(testOutputDir, 'my-page.html'), 'utf-8');
    expect(html).toContain('my-page');
  });

  it('should render markdown links correctly', () => {
    const mdContent = `---
title: Links
---
[Link text](https://example.com)`;

    fs.writeFileSync(path.join(testContentDir, 'links.md'), mdContent);
    build(testContentDir, testOutputDir);

    const html = fs.readFileSync(path.join(testOutputDir, 'links.html'), 'utf-8');
    expect(html).toContain('https://example.com');
    expect(html).toContain('Link text');
  });

  it('should render markdown emphasis correctly', () => {
    const mdContent = `---
title: Emphasis
---
**bold** and *italic* and ***bold italic***`;

    fs.writeFileSync(path.join(testContentDir, 'emphasis.md'), mdContent);
    build(testContentDir, testOutputDir);

    const html = fs.readFileSync(path.join(testOutputDir, 'emphasis.html'), 'utf-8');
    expect(html).toContain('<strong>bold</strong>');
    expect(html).toContain('<em>italic</em>');
  });
});
