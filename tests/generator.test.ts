import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { build } from '../src/generator';

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function writeFile(filePath: string, content: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content, 'utf8');
}

function writeFixtureTemplates(templatesDir: string): void {
  writeFile(path.join(templatesDir, 'partials', 'nav.hbs'), '<nav><a href="index.html">Back</a></nav>');
  writeFile(path.join(templatesDir, 'partials', 'header.hbs'), '<h1>{{title}}</h1>');
  writeFile(path.join(templatesDir, 'partials', 'footer.hbs'), '<footer>site-footer</footer>');

  writeFile(
    path.join(templatesDir, 'layouts', 'default.hbs'),
    `<!DOCTYPE html>
<html><head><title>{{title}}</title></head>
<body>
{{> nav}}
<article>
  {{> header}}
  {{#if date}}<p class="date">{{date}}</p>{{/if}}
  {{#each tags}}<span class="tag">{{this}}</span>{{/each}}
  {{{body}}}
</article>
{{> footer}}
</body></html>`
  );

  writeFile(
    path.join(templatesDir, 'layouts', 'post.hbs'),
    `<!DOCTYPE html>
<html class="layout-post"><head><title>{{title}} | Post</title></head>
<body>
{{> nav}}
<article class="post">
  {{> header}}
  {{{body}}}
</article>
{{> footer}}
</body></html>`
  );
}

describe('build', () => {
  let contentDir: string;
  let outputDir: string;
  let templatesDir: string;

  beforeEach(() => {
    contentDir = makeTempDir('ssg-content-');
    outputDir = makeTempDir('ssg-output-');
    templatesDir = makeTempDir('ssg-templates-');
    writeFixtureTemplates(templatesDir);

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
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  it('throws when the content directory does not exist', () => {
    expect(() =>
      build({ contentDir: path.join(contentDir, 'nope'), outputDir, templatesDir })
    ).toThrow();
  });

  it('throws when the templates directory does not exist', () => {
    expect(() =>
      build({ contentDir, outputDir, templatesDir: path.join(templatesDir, 'nope') })
    ).toThrow();
  });

  it('generates a page for every Markdown file, including nested ones', () => {
    const result = build({ contentDir, outputDir, templatesDir });

    expect(result.pages).toHaveLength(3);
    expect(fs.existsSync(path.join(outputDir, 'first-post.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'second-post.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'nested-third-post.html'))).toBe(true);
  });

  it('generates an index.html listing all pages', () => {
    build({ contentDir, outputDir, templatesDir });

    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8');
    expect(indexHtml).toContain('First Post');
    expect(indexHtml).toContain('Second Post');
    expect(indexHtml).toContain('Nested Post');
    expect(indexHtml).toContain('href="first-post.html"');
    expect(indexHtml).toContain('href="second-post.html"');
    expect(indexHtml).toContain('href="nested-third-post.html"');
  });

  it('renders frontmatter metadata and markdown body into each page using the default layout', () => {
    build({ contentDir, outputDir, templatesDir });

    const pageHtml = fs.readFileSync(path.join(outputDir, 'first-post.html'), 'utf8');
    expect(pageHtml).toContain('<h1>First Post</h1>');
    expect(pageHtml).toContain('2024-03-01');
    expect(pageHtml).toContain('<span class="tag">intro</span>');
    expect(pageHtml).toContain('<h1>Welcome</h1>');
    expect(pageHtml).toContain('<strong>first</strong>');
    expect(pageHtml).toContain('site-footer');
  });

  it('sorts pages by date descending, undated pages last', () => {
    const result = build({ contentDir, outputDir, templatesDir });
    const titles = result.pages.map((p) => p.title);
    expect(titles).toEqual(['Second Post', 'First Post', 'Nested Post']);
  });

  it('renders a page with a custom layout specified in frontmatter', () => {
    fs.writeFileSync(
      path.join(contentDir, 'custom-layout.md'),
      `---
title: Custom Layout Post
layout: post
---
Custom body.
`
    );

    build({ contentDir, outputDir, templatesDir });

    const pageHtml = fs.readFileSync(path.join(outputDir, 'custom-layout.html'), 'utf8');
    expect(pageHtml).toContain('class="layout-post"');
    expect(pageHtml).toContain('<title>Custom Layout Post | Post</title>');
    expect(pageHtml).toContain('Custom body.');
  });

  it('throws a clear error when frontmatter references an unknown layout', () => {
    fs.writeFileSync(
      path.join(contentDir, 'bad-layout.md'),
      `---
title: Bad Layout
layout: does-not-exist
---
Body.
`
    );

    expect(() => build({ contentDir, outputDir, templatesDir })).toThrow(/does-not-exist/);
  });

  it('defaults the templates directory to ./templates relative to the current working directory', () => {
    const cwdDir = makeTempDir('ssg-cwd-');
    writeFixtureTemplates(path.join(cwdDir, 'templates'));
    const previousCwd = process.cwd();

    try {
      process.chdir(cwdDir);
      const result = build({ contentDir, outputDir });
      expect(result.pages).toHaveLength(3);

      const pageHtml = fs.readFileSync(path.join(outputDir, 'first-post.html'), 'utf8');
      expect(pageHtml).toContain('<h1>First Post</h1>');
    } finally {
      process.chdir(previousCwd);
      fs.rmSync(cwdDir, { recursive: true, force: true });
    }
  });
});
