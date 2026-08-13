import fs from 'fs';
import path from 'path';
import {
  readMarkdownFiles,
  parseMarkdownFile,
  generatePages,
  generatePageHtml,
  generateIndexHtml,
} from './generator';

const TEST_CONTENT_DIR = path.join(__dirname, '__test-content');
const TEST_OUTPUT_DIR = path.join(__dirname, '__test-output');

function setupTestDir(): void {
  if (fs.existsSync(TEST_CONTENT_DIR)) {
    fs.rmSync(TEST_CONTENT_DIR, { recursive: true });
  }
  fs.mkdirSync(TEST_CONTENT_DIR, { recursive: true });

  if (fs.existsSync(TEST_OUTPUT_DIR)) {
    fs.rmSync(TEST_OUTPUT_DIR, { recursive: true });
  }
}

function cleanupTestDir(): void {
  if (fs.existsSync(TEST_CONTENT_DIR)) {
    fs.rmSync(TEST_CONTENT_DIR, { recursive: true });
  }
  if (fs.existsSync(TEST_OUTPUT_DIR)) {
    fs.rmSync(TEST_OUTPUT_DIR, { recursive: true });
  }
}

describe('Markdown File Reader', () => {
  beforeEach(setupTestDir);
  afterEach(cleanupTestDir);

  it('should read markdown files from directory', async () => {
    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'file1.md'), '# Test');
    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'file2.md'), '# Test 2');
    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'file3.txt'), 'Not markdown');

    const files = await readMarkdownFiles(TEST_CONTENT_DIR);

    expect(files).toContain('file1.md');
    expect(files).toContain('file2.md');
    expect(files).not.toContain('file3.txt');
    expect(files.length).toBe(2);
  });

  it('should throw error for non-existent directory', async () => {
    await expect(readMarkdownFiles('/nonexistent/path')).rejects.toThrow(
      'Content directory not found'
    );
  });

  it('should return empty array for empty directory', async () => {
    const files = await readMarkdownFiles(TEST_CONTENT_DIR);
    expect(files).toEqual([]);
  });
});

describe('Markdown File Parser', () => {
  beforeEach(setupTestDir);
  afterEach(cleanupTestDir);

  it('should parse markdown file with frontmatter', async () => {
    const content = `---
title: Test Post
date: 2023-01-01
tags: [test, demo]
---
# Heading

This is content.`;

    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'test.md'), content);
    const result = await parseMarkdownFile(path.join(TEST_CONTENT_DIR, 'test.md'));

    expect(result.slug).toBe('test');
    expect(result.filename).toBe('test.md');
    expect(result.frontmatter.title).toBe('Test Post');
    expect(result.frontmatter.date).toBe('2023-01-01');
    expect(result.frontmatter.tags).toEqual(['test', 'demo']);
    expect(result.content).toContain('# Heading');
    expect(result.html).toContain('<h1>Heading</h1>');
  });

  it('should parse markdown file without frontmatter', async () => {
    const content = '# Just Heading\n\nSome content';

    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'simple.md'), content);
    const result = await parseMarkdownFile(path.join(TEST_CONTENT_DIR, 'simple.md'));

    expect(result.slug).toBe('simple');
    expect(result.frontmatter).toEqual({});
    expect(result.html).toContain('<h1>Just Heading</h1>');
  });

  it('should escape HTML in title', async () => {
    const content = `---
title: <script>alert('xss')</script>
---
Content`;

    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'xss.md'), content);
    const result = await parseMarkdownFile(path.join(TEST_CONTENT_DIR, 'xss.md'));
    const html = generatePageHtml(result);

    expect(html).not.toContain('<script>');
    expect(html).toContain('&lt;script&gt;');
  });
});

describe('Page HTML Generation', () => {
  it('should generate page HTML with title', () => {
    const page = {
      slug: 'test',
      filename: 'test.md',
      frontmatter: { title: 'Test Page' },
      content: '# Content',
      html: '<h1>Content</h1>',
    };

    const html = generatePageHtml(page);

    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<title>Test Page</title>');
    expect(html).toContain('<h1>Test Page</h1>');
    expect(html).toContain('<h1>Content</h1>');
    expect(html).toContain('← Back to Index');
  });

  it('should generate page HTML without frontmatter title', () => {
    const page = {
      slug: 'untitled',
      filename: 'untitled.md',
      frontmatter: {},
      content: '# Content',
      html: '<h1>Content</h1>',
    };

    const html = generatePageHtml(page);

    expect(html).toContain('<title>untitled</title>');
    expect(html).toContain('<h1>untitled</h1>');
  });

  it('should include date in page HTML', () => {
    const page = {
      slug: 'dated',
      filename: 'dated.md',
      frontmatter: { title: 'Dated Page', date: '2023-01-15' },
      content: 'Content',
      html: '<p>Content</p>',
    };

    const html = generatePageHtml(page);

    expect(html).toContain('<p class="date">2023-01-15</p>');
  });

  it('should include tags in page HTML', () => {
    const page = {
      slug: 'tagged',
      filename: 'tagged.md',
      frontmatter: { title: 'Tagged Page', tags: ['typescript', 'testing'] },
      content: 'Content',
      html: '<p>Content</p>',
    };

    const html = generatePageHtml(page);

    expect(html).toContain('class="tags"');
    expect(html).toContain('class="tag"');
    expect(html).toContain('typescript');
    expect(html).toContain('testing');
  });

  it('should escape tag values', () => {
    const page = {
      slug: 'xss-tags',
      filename: 'xss-tags.md',
      frontmatter: { title: 'XSS', tags: ['<script>alert("xss")</script>'] },
      content: 'Content',
      html: '<p>Content</p>',
    };

    const html = generatePageHtml(page);

    expect(html).not.toContain('<script>');
    expect(html).toContain('&lt;script&gt;');
  });
});

describe('Index HTML Generation', () => {
  it('should generate index HTML with page links', () => {
    const pages = [
      {
        slug: 'page1',
        filename: 'page1.md',
        frontmatter: { title: 'First Page', date: '2023-01-01' },
        content: '',
        html: '',
      },
      {
        slug: 'page2',
        filename: 'page2.md',
        frontmatter: { title: 'Second Page', date: '2023-01-02' },
        content: '',
        html: '',
      },
    ];

    const html = generateIndexHtml(pages);

    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<h1>Site Index</h1>');
    expect(html).toContain('href="page1.html"');
    expect(html).toContain('href="page2.html"');
    expect(html).toContain('First Page');
    expect(html).toContain('Second Page');
  });

  it('should sort pages by date in descending order', () => {
    const pages = [
      {
        slug: 'old',
        filename: 'old.md',
        frontmatter: { title: 'Old Post', date: '2023-01-01' },
        content: '',
        html: '',
      },
      {
        slug: 'new',
        filename: 'new.md',
        frontmatter: { title: 'New Post', date: '2023-01-15' },
        content: '',
        html: '',
      },
      {
        slug: 'middle',
        filename: 'middle.md',
        frontmatter: { title: 'Middle Post', date: '2023-01-08' },
        content: '',
        html: '',
      },
    ];

    const html = generateIndexHtml(pages);
    const newPos = html.indexOf('New Post');
    const middlePos = html.indexOf('Middle Post');
    const oldPos = html.indexOf('Old Post');

    expect(newPos).toBeLessThan(middlePos);
    expect(middlePos).toBeLessThan(oldPos);
  });

  it('should handle pages without dates', () => {
    const pages = [
      {
        slug: 'no-date',
        filename: 'no-date.md',
        frontmatter: { title: 'No Date Post' },
        content: '',
        html: '',
      },
      {
        slug: 'dated',
        filename: 'dated.md',
        frontmatter: { title: 'Dated Post', date: '2023-01-01' },
        content: '',
        html: '',
      },
    ];

    const html = generateIndexHtml(pages);

    expect(html).toContain('No Date Post');
    expect(html).toContain('Dated Post');
  });

  it('should escape page titles in index', () => {
    const pages = [
      {
        slug: 'xss',
        filename: 'xss.md',
        frontmatter: { title: '<script>alert("xss")</script>' },
        content: '',
        html: '',
      },
    ];

    const html = generateIndexHtml(pages);

    expect(html).not.toContain('<script>');
    expect(html).toContain('&lt;script&gt;');
  });

  it('should handle empty page list', () => {
    const html = generateIndexHtml([]);

    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<h1>Site Index</h1>');
    expect(html).not.toContain('href=');
  });
});

describe('Full Site Generation', () => {
  beforeEach(setupTestDir);
  afterEach(cleanupTestDir);

  it('should generate all pages and index', async () => {
    const page1 = `---
title: Page One
date: 2023-01-01
---
# First Page`;

    const page2 = `---
title: Page Two
date: 2023-01-02
---
# Second Page`;

    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'page1.md'), page1);
    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'page2.md'), page2);

    const pages = await generatePages(TEST_CONTENT_DIR, TEST_OUTPUT_DIR);

    expect(pages.length).toBe(2);
    expect(fs.existsSync(path.join(TEST_OUTPUT_DIR, 'page1.html'))).toBe(true);
    expect(fs.existsSync(path.join(TEST_OUTPUT_DIR, 'page2.html'))).toBe(true);

    const page1Html = fs.readFileSync(path.join(TEST_OUTPUT_DIR, 'page1.html'), 'utf-8');
    expect(page1Html).toContain('Page One');
    expect(page1Html).toContain('← Back to Index');

    const page2Html = fs.readFileSync(path.join(TEST_OUTPUT_DIR, 'page2.html'), 'utf-8');
    expect(page2Html).toContain('Page Two');
  });

  it('should handle single page', async () => {
    const content = `---
title: Only Page
---
Content`;

    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'only.md'), content);

    const pages = await generatePages(TEST_CONTENT_DIR, TEST_OUTPUT_DIR);

    expect(pages.length).toBe(1);
    expect(pages[0].slug).toBe('only');
    expect(pages[0].frontmatter.title).toBe('Only Page');
  });

  it('should handle empty content directory', async () => {
    const pages = await generatePages(TEST_CONTENT_DIR, TEST_OUTPUT_DIR);

    expect(pages).toEqual([]);
  });
});
