import fs from 'fs';
import os from 'os';
import path from 'path';
import { buildSite } from '../src/cli';

const POST = `---
title: Templated Post
date: 2024-06-01
template: post
---
# Templated Post

Rendered through **templates**.
`;

const PLAIN = `---
title: Plain Page
date: 2024-06-02
---
No template here.
`;

const INDEX = `---
title: Home
---
Welcome home.
`;

const DEFAULT_TEMPLATE = `<html>
<head><title>{{title}}</title></head>
<body class="default-tpl">
  <div class="page">{{{body}}}</div>
</body>
</html>
`;

const BASE_LAYOUT = `<!DOCTYPE html>
<html>
<head><title>{{title}}</title></head>
<body>
  {{> header}}
  {{{body}}}
  {{> footer}}
</body>
</html>
`;

const HEADER_PARTIAL = `<header class="site-header">My Site</header>
<nav>{{#each site.pages}}<a href="./{{outputFile}}">{{title}}</a>{{/each}}</nav>
`;

const FOOTER_PARTIAL = `<footer class="site-footer">Bye</footer>`;

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-tpl-'));
}

function writeFiles(root: string, files: Record<string, string>): void {
  for (const [name, contents] of Object.entries(files)) {
    const file = path.join(root, name);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, contents, 'utf-8');
  }
}

function read(dir: string, file: string): string {
  return fs.readFileSync(path.join(dir, file), 'utf-8');
}

function cleanup(dir: string): void {
  fs.rmSync(dir, { recursive: true, force: true });
}

describe('buildSite with templates', () => {
  let root: string;
  let contentDir: string;
  let templatesDir: string;
  let outputDir: string;

  beforeEach(() => {
    root = makeTempDir();
    contentDir = path.join(root, 'content');
    templatesDir = path.join(root, 'templates');
    outputDir = path.join(root, 'dist');
  });

  afterEach(() => {
    cleanup(root);
  });

  it('applies the default template when no template is specified', () => {
    writeFiles(contentDir, { 'plain.md': PLAIN });
    writeFiles(templatesDir, { 'default.hbs': DEFAULT_TEMPLATE });

    buildSite(contentDir, outputDir, templatesDir);

    const html = read(outputDir, 'plain.html');
    expect(html).toContain('class="default-tpl"');
    expect(html).toContain('<title>Plain Page</title>');
    expect(html).toContain('No template here.');
  });

  it('uses the per-page template selected from frontmatter', () => {
    writeFiles(contentDir, { 'post.md': POST });
    writeFiles(templatesDir, {
      'default.hbs': DEFAULT_TEMPLATE,
      'post.hbs': `<article class="post-tpl"><h1>{{title}}</h1>{{{body}}}</article>`,
    });

    buildSite(contentDir, outputDir, templatesDir);

    const html = read(outputDir, 'post.html');
    expect(html).toContain('class="post-tpl"');
    expect(html).toContain('<h1>Templated Post</h1>');
    expect(html).toContain('<strong>templates</strong>');
    expect(html).not.toContain('class="default-tpl"');
  });

  it('wraps templated pages in a layout with partials', () => {
    writeFiles(contentDir, { 'post.md': POST });
    writeFiles(templatesDir, {
      'post.hbs': `---
layout: base
---
<article class="post-content">{{{body}}}</article>`,
      'layouts/base.hbs': BASE_LAYOUT,
      'partials/header.hbs': HEADER_PARTIAL,
      'partials/footer.hbs': FOOTER_PARTIAL,
    });

    buildSite(contentDir, outputDir, templatesDir);

    const html = read(outputDir, 'post.html');
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<header class="site-header">My Site</header>');
    expect(html).toContain('<footer class="site-footer">Bye</footer>');
    expect(html).toContain('class="post-content"');
    expect(html).toContain('<strong>templates</strong>');
  });

  it('exposes every generated page to the nav partial', () => {
    writeFiles(contentDir, {
      'post.md': POST,
      'plain.md': PLAIN,
    });
    writeFiles(templatesDir, {
      'post.hbs': `---
layout: base
---
<article class="post-content">{{{body}}}</article>`,
      'layouts/base.hbs': BASE_LAYOUT,
      'partials/header.hbs': HEADER_PARTIAL,
      'partials/footer.hbs': FOOTER_PARTIAL,
    });

    buildSite(contentDir, outputDir, templatesDir);

    const html = read(outputDir, 'post.html');
    expect(html).toContain('<a href="./post.html">Templated Post</a>');
    expect(html).toContain('<a href="./plain.html">Plain Page</a>');
  });

  it('uses a layout declared in the page frontmatter', () => {
    const bare = `---
title: Bare Page
layout: bare
template: default
---
Bare bones.
`;
    writeFiles(contentDir, { 'bare.md': bare });
    writeFiles(templatesDir, {
      'default.hbs': `<main>{{{body}}}</main>`,
      'layouts/bare.hbs': `<div class="bare-layout">{{{body}}}</div>`,
    });

    buildSite(contentDir, outputDir, templatesDir);

    const html = read(outputDir, 'bare.html');
    expect(html).toContain('class="bare-layout"');
    expect(html).toContain('<main>');
    expect(html).toContain('Bare bones.');
  });

  it('falls back to the default template for missing named templates', () => {
    const ghost = `---
title: Ghost
template: does-not-exist
---
Boo.
`;
    writeFiles(contentDir, { 'ghost.md': ghost });
    writeFiles(templatesDir, { 'default.hbs': DEFAULT_TEMPLATE });

    buildSite(contentDir, outputDir, templatesDir);

    const html = read(outputDir, 'ghost.html');
    expect(html).toContain('class="default-tpl"');
    expect(html).toContain('Boo.');
  });

  it('leaves the generated index untouched by templates', () => {
    writeFiles(contentDir, { 'post.md': POST, 'index.md': INDEX });
    writeFiles(templatesDir, { 'post.hbs': '<article>{{{body}}}</article>' });

    buildSite(contentDir, outputDir, templatesDir);

    const index = read(outputDir, 'index.html');
    expect(index).toContain('<title>All pages</title>');
    expect(index).toContain('<a href="./post.html">');
  });

  it('keeps the built-in generator behaviour when no templates directory exists', () => {
    writeFiles(contentDir, { 'post.md': POST });

    buildSite(contentDir, outputDir, templatesDir);

    const html = read(outputDir, 'post.html');
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<style>');
    expect(html).toContain('<a class="back" href="./index.html">');
  });
});
