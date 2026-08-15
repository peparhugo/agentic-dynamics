import fs from 'fs';
import os from 'os';
import path from 'path';
import { build, buildPage, findMarkdownFiles } from '../src/build';

function makeTmpDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

describe('static site build', () => {
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    contentDir = makeTmpDir('ssg-content-');
    outputDir = makeTmpDir('ssg-dist-');
    fs.writeFileSync(
      path.join(contentDir, 'first-post.md'),
      `---
title: First Post
date: 2024-01-01
tags: [intro, news]
---
# Hello

This is the **first** post.`
    );
    fs.writeFileSync(
      path.join(contentDir, 'second-post.md'),
      `---
title: Second Post
date: 2024-02-01
tags: update
---
Some more content here.`
    );
    fs.writeFileSync(path.join(contentDir, 'no-frontmatter.md'), '# No Frontmatter\n\nJust text.');
    fs.writeFileSync(
      path.join(contentDir, 'blog-post.md'),
      `---
title: Blog Post
date: 2024-03-01
template: post
---
Posted with the post layout.`
    );
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  it('finds all markdown files in the content directory, sorted', () => {
    const files = findMarkdownFiles(contentDir);
    expect(files).toEqual(['blog-post.md', 'first-post.md', 'no-frontmatter.md', 'second-post.md']);
  });

  it('throws when the content directory does not exist', () => {
    expect(() => findMarkdownFiles(path.join(contentDir, 'missing'))).toThrow(/Content directory not found/);
  });

  it('builds a single page with frontmatter applied', () => {
    const page = buildPage(contentDir, 'first-post.md');
    expect(page.title).toBe('First Post');
    expect(page.date).toBe('2024-01-01');
    expect(page.tags).toEqual(['intro', 'news']);
    expect(page.outputPath).toBe('first-post.html');
    expect(page.html).toContain('<h1>First Post</h1>');
    expect(page.html).toContain('<strong>first</strong>');
  });

  it('falls back to the filename slug as title when frontmatter has none', () => {
    const page = buildPage(contentDir, 'no-frontmatter.md');
    expect(page.title).toBe('no-frontmatter');
    expect(page.html).toContain('<h1>No Frontmatter</h1>');
  });

  it('normalizes a single string tag into an array', () => {
    const page = buildPage(contentDir, 'second-post.md');
    expect(page.tags).toEqual(['update']);
  });

  it('writes an HTML file per page plus an index.html to the output directory', () => {
    const result = build({ contentDir, outputDir });
    expect(result.pages).toHaveLength(4);

    const distFiles = fs.readdirSync(outputDir).sort();
    expect(distFiles).toEqual(
      ['blog-post.html', 'first-post.html', 'index.html', 'no-frontmatter.html', 'second-post.html'].sort()
    );

    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(indexHtml).toContain('First Post');
    expect(indexHtml).toContain('Second Post');
    expect(indexHtml).toContain('href="first-post.html"');
  });

  it('creates the output directory if it does not exist', () => {
    const nestedOutput = path.join(outputDir, 'nested', 'dist');
    build({ contentDir, outputDir: nestedOutput });
    expect(fs.existsSync(path.join(nestedOutput, 'index.html'))).toBe(true);
  });

  it('defaults to the "default" template when none is specified in frontmatter', () => {
    const page = buildPage(contentDir, 'first-post.md');
    expect(page.template).toBe('default');
  });

  it('uses the layout named in frontmatter "template" and renders page-specific markup', () => {
    const page = buildPage(contentDir, 'blog-post.md');
    expect(page.template).toBe('post');
    expect(page.html).toContain('class="post"');
    expect(page.html).toContain('Posted on 2024-03-01');
  });

  it('renders header/nav/footer partials into every page via the shared layouts', () => {
    const page = buildPage(contentDir, 'first-post.md');
    expect(page.html).toContain('<header>');
    expect(page.html).toContain('<a href="index.html">Home</a>');
    expect(page.html).toContain('<footer>');
  });

  it('renders the index page through templates/index.hbs, including shared partials', () => {
    const result = build({ contentDir, outputDir });
    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(indexHtml).toContain('<a href="index.html">Home</a>');
    expect(indexHtml).toContain('All Pages');
  });

  it('throws a clear error when frontmatter references a template with no matching layout file', () => {
    fs.writeFileSync(
      path.join(contentDir, 'broken.md'),
      `---
title: Broken
template: does-not-exist
---
Body`
    );
    expect(() => buildPage(contentDir, 'broken.md')).toThrow(/Unknown template "does-not-exist"/);
  });

  it('supports a custom templatesDir so different sites can use different template sets', () => {
    const customTemplatesDir = makeTmpDir('ssg-custom-templates-');
    fs.mkdirSync(path.join(customTemplatesDir, 'layouts'));
    fs.writeFileSync(
      path.join(customTemplatesDir, 'layouts', 'default.hbs'),
      '<custom-layout>{{{body}}}</custom-layout>'
    );
    const page = buildPage(contentDir, 'first-post.md', customTemplatesDir);
    expect(page.html).toContain('<custom-layout>');
    fs.rmSync(customTemplatesDir, { recursive: true, force: true });
  });
});
