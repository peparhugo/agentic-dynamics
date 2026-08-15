import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { SiteGenerator } from '../src/generator';

describe('SiteGenerator', () => {
  let tempDir: string;
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-test-'));
    contentDir = path.join(tempDir, 'content');
    outputDir = path.join(tempDir, 'dist');
    fs.mkdirSync(contentDir);
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('should generate HTML files from markdown', async () => {
    const markdownContent = `---
title: Test Post
date: 2024-01-15
tags: test, markdown
---

# Test Post

This is a test post.`;

    fs.writeFileSync(path.join(contentDir, 'test.md'), markdownContent);

    const generator = new SiteGenerator({ contentDir, outputDir });
    await generator.build();

    const outputFile = path.join(outputDir, 'test.html');
    expect(fs.existsSync(outputFile)).toBe(true);

    const content = fs.readFileSync(outputFile, 'utf-8');
    expect(content).toContain('<title>Test Post</title>');
    expect(content).toContain('<h1>Test Post</h1>');
    expect(content).toContain('This is a test post.');
  });

  it('should generate index.html with all pages', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'first.md'),
      `---
title: First Page
date: 2024-01-01
---

Content of first page.`
    );

    fs.writeFileSync(
      path.join(contentDir, 'second.md'),
      `---
title: Second Page
date: 2024-01-02
tags: important
---

Content of second page.`
    );

    const generator = new SiteGenerator({ contentDir, outputDir });
    await generator.build();

    const indexFile = path.join(outputDir, 'index.html');
    expect(fs.existsSync(indexFile)).toBe(true);

    const indexContent = fs.readFileSync(indexFile, 'utf-8');
    expect(indexContent).toContain('First Page');
    expect(indexContent).toContain('Second Page');
    expect(indexContent).toContain('first.html');
    expect(indexContent).toContain('second.html');
    expect(indexContent).toContain('2024-01-01');
    expect(indexContent).toContain('2024-01-02');
    expect(indexContent).toContain('important');
  });

  it('should handle markdown without frontmatter', async () => {
    const markdownContent = `# No Frontmatter

Just plain markdown.`;

    fs.writeFileSync(path.join(contentDir, 'plain.md'), markdownContent);

    const generator = new SiteGenerator({ contentDir, outputDir });
    await generator.build();

    const outputFile = path.join(outputDir, 'plain.html');
    expect(fs.existsSync(outputFile)).toBe(true);

    const content = fs.readFileSync(outputFile, 'utf-8');
    expect(content).toContain('<title>plain</title>');
  });

  it('should create output directory if it does not exist', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'test.md'),
      `---
title: Test
---

Content.`
    );

    expect(fs.existsSync(outputDir)).toBe(false);

    const generator = new SiteGenerator({ contentDir, outputDir });
    await generator.build();

    expect(fs.existsSync(outputDir)).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'test.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
  });

  it('should handle empty content directory', async () => {
    const generator = new SiteGenerator({ contentDir, outputDir });
    await generator.build();

    expect(fs.existsSync(outputDir)).toBe(true);

    const indexFile = path.join(outputDir, 'index.html');
    expect(fs.existsSync(indexFile)).toBe(true);

    const indexContent = fs.readFileSync(indexFile, 'utf-8');
    expect(indexContent).toContain('No pages found');
  });

  it('should only process .md files', async () => {
    fs.writeFileSync(path.join(contentDir, 'markdown.md'), '# Markdown\n\nContent.');
    fs.writeFileSync(path.join(contentDir, 'text.txt'), 'This should not be processed.');
    fs.writeFileSync(path.join(contentDir, 'code.js'), 'console.log("ignored");');

    const generator = new SiteGenerator({ contentDir, outputDir });
    await generator.build();

    expect(fs.existsSync(path.join(outputDir, 'markdown.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'text.html'))).toBe(false);
    expect(fs.existsSync(path.join(outputDir, 'code.html'))).toBe(false);
  });

  it('should sort markdown files alphabetically', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'zebra.md'),
      '---\ntitle: Zebra\n---\nZ'
    );
    fs.writeFileSync(
      path.join(contentDir, 'apple.md'),
      '---\ntitle: Apple\n---\nA'
    );
    fs.writeFileSync(
      path.join(contentDir, 'banana.md'),
      '---\ntitle: Banana\n---\nB'
    );

    const generator = new SiteGenerator({ contentDir, outputDir });
    await generator.build();

    const indexContent = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    const applePos = indexContent.indexOf('Apple');
    const bananaPos = indexContent.indexOf('Banana');
    const zebraPos = indexContent.indexOf('Zebra');

    expect(applePos).toBeLessThan(bananaPos);
    expect(bananaPos).toBeLessThan(zebraPos);
  });

  it('should escape HTML in titles', async () => {
    const markdownContent = `---
title: <script>alert('xss')</script>
---

Normal content.`;

    fs.writeFileSync(path.join(contentDir, 'xss.md'), markdownContent);

    const generator = new SiteGenerator({ contentDir, outputDir });
    await generator.build();

    const content = fs.readFileSync(path.join(outputDir, 'xss.html'), 'utf-8');
    expect(content).toContain('&lt;script&gt;');
    expect(content).toContain('&lt;/script&gt;');
    expect(content).not.toContain('<title><script>');
  });

  it('should include navigation link to index from page', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'page.md'),
      '---\ntitle: Page\n---\nContent.'
    );

    const generator = new SiteGenerator({ contentDir, outputDir });
    await generator.build();

    const content = fs.readFileSync(path.join(outputDir, 'page.html'), 'utf-8');
    expect(content).toContain('index.html');
    expect(content).toContain('← Home');
  });

  it('should display tags in index', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'tagged.md'),
      '---\ntitle: Tagged Post\ntags: typescript, testing, cli\n---\nContent.'
    );

    const generator = new SiteGenerator({ contentDir, outputDir });
    await generator.build();

    const indexContent = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(indexContent).toContain('typescript');
    expect(indexContent).toContain('testing');
    expect(indexContent).toContain('cli');
  });
});
