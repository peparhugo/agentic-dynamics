import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { build } from '../src/generator';

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

describe('build', () => {
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    contentDir = makeTempDir('ssg-content-');
    outputDir = makeTempDir('ssg-output-');

    fs.writeFileSync(
      path.join(contentDir, 'first-post.md'),
      `---
title: First Post
date: 2024-03-01
tags: [intro, news]
---
# Welcome

This is the **first** post.
`
    );

    fs.writeFileSync(
      path.join(contentDir, 'second-post.md'),
      `---
title: Second Post
date: 2024-05-10
tags: [update]
---
Some more content here.
`
    );

    fs.mkdirSync(path.join(contentDir, 'nested'));
    fs.writeFileSync(
      path.join(contentDir, 'nested', 'third-post.md'),
      `---
title: Nested Post
---
Nested content.
`
    );
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  it('throws when the content directory does not exist', () => {
    expect(() =>
      build({ contentDir: path.join(contentDir, 'nope'), outputDir })
    ).toThrow();
  });

  it('generates a page for every Markdown file, including nested ones', () => {
    const result = build({ contentDir, outputDir });

    expect(result.pages).toHaveLength(3);
    expect(fs.existsSync(path.join(outputDir, 'first-post.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'second-post.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'nested-third-post.html'))).toBe(true);
  });

  it('generates an index.html listing all pages', () => {
    build({ contentDir, outputDir });

    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8');
    expect(indexHtml).toContain('First Post');
    expect(indexHtml).toContain('Second Post');
    expect(indexHtml).toContain('Nested Post');
    expect(indexHtml).toContain('href="first-post.html"');
    expect(indexHtml).toContain('href="second-post.html"');
    expect(indexHtml).toContain('href="nested-third-post.html"');
  });

  it('renders frontmatter metadata and markdown body into each page', () => {
    build({ contentDir, outputDir });

    const pageHtml = fs.readFileSync(path.join(outputDir, 'first-post.html'), 'utf8');
    expect(pageHtml).toContain('<h1>First Post</h1>');
    expect(pageHtml).toContain('2024-03-01');
    expect(pageHtml).toContain('<span class="tag">intro</span>');
    expect(pageHtml).toContain('<h1>Welcome</h1>');
    expect(pageHtml).toContain('<strong>first</strong>');
  });

  it('sorts pages by date descending, undated pages last', () => {
    const result = build({ contentDir, outputDir });
    const titles = result.pages.map((p) => p.title);
    expect(titles).toEqual(['Second Post', 'First Post', 'Nested Post']);
  });
});
