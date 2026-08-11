import fs from 'fs';
import path from 'path';
import os from 'os';
import { buildSite } from '../generator';

function setupContentDir(files: Record<string, string>): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-test-'));
  for (const [name, content] of Object.entries(files)) {
    fs.writeFileSync(path.join(dir, name), content, 'utf-8');
  }
  return dir;
}

describe('buildSite', () => {
  let outputDir: string;

  beforeEach(() => {
    outputDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-output-'));
  });

  afterEach(() => {
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  test('throws if content directory does not exist', () => {
    expect(() => buildSite('/nonexistent/path', outputDir)).toThrow(
      'Content directory does not exist'
    );
  });

  test('creates output directory if it does not exist', () => {
    const contentDir = setupContentDir({
      'hello.md': `---
title: Hello World
date: 2024-01-01
---

# Hello

This is a test.
`,
    });

    const outDir = path.join(outputDir, 'nested', 'sub');
    buildSite(contentDir, outDir);
    expect(fs.existsSync(outDir)).toBe(true);
    fs.rmSync(contentDir, { recursive: true, force: true });
  });

  test('parses frontmatter and generates HTML page', () => {
    const contentDir = setupContentDir({
      'hello.md': `---
title: Hello World
date: 2024-01-15
tags:
  - test
  - ssg
---

# Hello

This is a **test**.
`,
    });

    buildSite(contentDir, outputDir);

    const pagePath = path.join(outputDir, 'hello.html');
    expect(fs.existsSync(pagePath)).toBe(true);

    const html = fs.readFileSync(pagePath, 'utf-8');
    expect(html).toContain('<title>Hello World</title>');
    expect(html).toContain('<h1>Hello World</h1>');
    expect(html).toContain('<h1>Hello</h1>');
    expect(html).toContain('<strong>test</strong>');
    expect(html).toContain('2024-01-15');
    expect(html).toContain('<span class="tag">test</span>');
    expect(html).toContain('<span class="tag">ssg</span>');
    expect(html).toContain('<article>');
    expect(html).toContain('</article>');

    fs.rmSync(contentDir, { recursive: true, force: true });
  });

  test('generates index.html listing all pages', () => {
    const contentDir = setupContentDir({
      'a.md': `---
title: Alpha
date: 2024-03-01
---

# Alpha
`,
      'b.md': `---
title: Beta
date: 2024-01-01
---

# Beta
`,
    });

    buildSite(contentDir, outputDir);

    const indexPath = path.join(outputDir, 'index.html');
    expect(fs.existsSync(indexPath)).toBe(true);

    const html = fs.readFileSync(indexPath, 'utf-8');
    expect(html).toContain('<title>Site Index</title>');
    expect(html).toContain('<a href="a.html">Alpha</a>');
    expect(html).toContain('<a href="b.html">Beta</a>');

    fs.rmSync(contentDir, { recursive: true, force: true });
  });

  test('uses Untitled as fallback title', () => {
    const contentDir = setupContentDir({
      'nometa.md': `# Just Content

No frontmatter here.
`,
    });

    buildSite(contentDir, outputDir);

    const pagePath = path.join(outputDir, 'nometa.html');
    const html = fs.readFileSync(pagePath, 'utf-8');
    expect(html).toContain('<title>Untitled</title>');
    expect(html).toContain('<h1>Untitled</h1>');

    fs.rmSync(contentDir, { recursive: true, force: true });
  });

  test('only processes .md files', () => {
    const contentDir = setupContentDir({
      'page.md': `---
title: Page
date: 2024-01-01
---

# Page
`,
      'readme.txt': 'not a markdown file',
    });

    buildSite(contentDir, outputDir);

    const files = fs.readdirSync(outputDir).filter((f) => f.endsWith('.html'));
    expect(files).toHaveLength(2);
    expect(files).toContain('page.html');
    expect(files).toContain('index.html');

    fs.rmSync(contentDir, { recursive: true, force: true });
  });

  test('handles empty tags gracefully', () => {
    const contentDir = setupContentDir({
      'page.md': `---
title: Page
date: 2024-01-01
---

# Page
`,
    });

    buildSite(contentDir, outputDir);

    const pagePath = path.join(outputDir, 'page.html');
    const html = fs.readFileSync(pagePath, 'utf-8');
    expect(html).toContain('<div class="tags">');
    expect(html).not.toContain('<span class="tag">');

    fs.rmSync(contentDir, { recursive: true, force: true });
  });

  test('handles empty date gracefully', () => {
    const contentDir = setupContentDir({
      'page.md': `---
title: Page
---

# Page
`,
    });

    buildSite(contentDir, outputDir);

    const pagePath = path.join(outputDir, 'page.html');
    const html = fs.readFileSync(pagePath, 'utf-8');
    expect(html).toContain('<p class="date"></p>');

    fs.rmSync(contentDir, { recursive: true, force: true });
  });

  test('sorts pages by date descending in index', () => {
    const contentDir = setupContentDir({
      'a.md': `---
title: Alpha
date: 2024-01-01
---

# Alpha
`,
      'b.md': `---
title: Beta
date: 2024-06-01
---

# Beta
`,
      'c.md': `---
title: Gamma
date: 2024-03-01
---

# Gamma
`,
    });

    buildSite(contentDir, outputDir);

    const html = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');

    const aIdx = html.indexOf('Alpha');
    const bIdx = html.indexOf('Beta');
    const cIdx = html.indexOf('Gamma');

    expect(bIdx).toBeLessThan(cIdx);
    expect(cIdx).toBeLessThan(aIdx);

    fs.rmSync(contentDir, { recursive: true, force: true });
  });

  test('escapes HTML in frontmatter values', () => {
    const contentDir = setupContentDir({
      'xss.md': `---
title: <script>alert("xss")</script>
date: 2024-01-01
---

# Content
`,
    });

    buildSite(contentDir, outputDir);

    const html = fs.readFileSync(path.join(outputDir, 'xss.html'), 'utf-8');
    expect(html).not.toContain('<script>alert');
    expect(html).toContain('&lt;script&gt;alert');

    fs.rmSync(contentDir, { recursive: true, force: true });
  });

  test('empty content directory produces only index.html', () => {
    const contentDir = setupContentDir({});
    buildSite(contentDir, outputDir);

    const files = fs.readdirSync(outputDir).filter((f) => f.endsWith('.html'));
    expect(files).toHaveLength(1);
    expect(files).toContain('index.html');

    fs.rmSync(contentDir, { recursive: true, force: true });
  });

  test('handles content directory with nested paths gracefully (only top-level)', () => {
    const contentDir = setupContentDir({
      'page.md': `---
title: Page
date: 2024-01-01
---

# Page
`,
    });

    const nestedDir = path.join(contentDir, 'subdir');
    fs.mkdirSync(nestedDir);
    fs.writeFileSync(
      path.join(nestedDir, 'nested.md'),
      `---
title: Nested
date: 2024-02-01
---

# Nested
`
    );

    buildSite(contentDir, outputDir);

    const files = fs.readdirSync(outputDir).filter((f) => f.endsWith('.html'));
    expect(files).toContain('page.html');
    expect(files).toContain('index.html');

    fs.rmSync(contentDir, { recursive: true, force: true });
  });
});
