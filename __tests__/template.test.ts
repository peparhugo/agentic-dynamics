import fs from 'fs';
import os from 'os';
import path from 'path';
import { build } from '../src/ssg';
import { TemplateEngine } from '../src/template';

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function writeTree(root: string, files: Record<string, string>): void {
  for (const [rel, content] of Object.entries(files)) {
    const filePath = path.join(root, rel);
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, content, 'utf8');
  }
}

describe('template engine', () => {
  it('renders pages with the default template and default layout', () => {
    const root = makeTempDir('ssg-tpl-');
    writeTree(root, {
      'content/home.md': `---
title: Home
date: 2024-01-01
---
Welcome **home**.`,
      'templates/default.hbs': `<article>{{title}}\n{{{html}}}</article>`,
      'templates/layouts/default.hbs': `<!DOCTYPE html>\n<title>{{title}}</title>\n<main>{{{body}}}</main>`,
    });
    const outputDir = path.join(root, 'dist');

    build({
      contentDir: path.join(root, 'content'),
      outputDir,
      templateDir: path.join(root, 'templates'),
    });

    const html = fs.readFileSync(path.join(outputDir, 'home.html'), 'utf8');
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<title>Home</title>');
    expect(html).toContain('<article>Home');
    expect(html).toContain('<strong>home</strong>');
    expect(html).not.toContain('{{{body}}}');
  });

  it('uses the template specified in frontmatter', () => {
    const root = makeTempDir('ssg-tpl-');
    writeTree(root, {
      'content/blog/hello.md': `---
title: Hello
template: post
---
Post body.`,
      'content/about.md': `---
title: About
---
About body.`,
      'templates/default.hbs': `<div class="plain">{{{html}}}</div>`,
      'templates/post.hbs': `<article class="post"><h1>{{title}}</h1>{{{html}}}</article>`,
      'templates/layouts/default.hbs': `{{{body}}}`,
    });
    const outputDir = path.join(root, 'dist');

    build({
      contentDir: path.join(root, 'content'),
      outputDir,
      templateDir: path.join(root, 'templates'),
    });

    const post = fs.readFileSync(path.join(outputDir, 'blog/hello.html'), 'utf8');
    expect(post).toContain('<article class="post">');
    expect(post).toContain('<h1>Hello</h1>');

    const about = fs.readFileSync(path.join(outputDir, 'about.html'), 'utf8');
    expect(about).toContain('<div class="plain">');
    expect(about).not.toContain('class="post"');
  });

  it('falls back to the default template when the named template is missing', () => {
    const root = makeTempDir('ssg-tpl-');
    writeTree(root, {
      'content/a.md': `---
title: A
template: missing
---
Body.`,
      'templates/default.hbs': `<div>DEFAULT {{title}} {{{html}}}</div>`,
    });
    const outputDir = path.join(root, 'dist');

    build({
      contentDir: path.join(root, 'content'),
      outputDir,
      templateDir: path.join(root, 'templates'),
    });

    const html = fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8');
    expect(html).toContain('<div>DEFAULT A');
  });

  it('wraps page content in a layout via the body placeholder', () => {
    const root = makeTempDir('ssg-tpl-');
    writeTree(root, {
      'content/page.md': `---
title: Page
layout: wide
---
Body text.`,
      'templates/default.hbs': `<section>{{{html}}}</section>`,
      'templates/layouts/default.hbs': `<!DOCTYPE html>\n<title>Default</title>\n{{{body}}}`,
      'templates/layouts/wide.hbs': `<!DOCTYPE html>\n<title>Wide</title>\n<div class="wide">{{{body}}}</div>`,
    });
    const outputDir = path.join(root, 'dist');

    build({
      contentDir: path.join(root, 'content'),
      outputDir,
      templateDir: path.join(root, 'templates'),
    });

    const html = fs.readFileSync(path.join(outputDir, 'page.html'), 'utf8');
    expect(html).toContain('<div class="wide">');
    expect(html).toContain('<section>');
    expect(html).toContain('Body text.');
    expect(html).not.toContain('<title>Default</title>');
  });

  it('renders partials from the partials directory', () => {
    const root = makeTempDir('ssg-tpl-');
    writeTree(root, {
      'content/p.md': `---
title: P
---
Hi.`,
      'templates/default.hbs': `{{{html}}}`,
      'templates/layouts/default.hbs': `<!DOCTYPE html>\n<body>\n{{> header}}\n{{{body}}}\n{{> footer}}\n</body>`,
      'templates/partials/header.hbs': `<header>{{> nav}}</header>`,
      'templates/partials/nav.hbs': `<a href="index.html">Home</a>`,
      'templates/partials/footer.hbs': `<footer>Footer</footer>`,
    });
    const outputDir = path.join(root, 'dist');

    build({
      contentDir: path.join(root, 'content'),
      outputDir,
      templateDir: path.join(root, 'templates'),
    });

    const html = fs.readFileSync(path.join(outputDir, 'p.html'), 'utf8');
    expect(html).toContain('<header><a href="index.html">Home</a></header>');
    expect(html).toContain('<footer>Footer</footer>');
  });

  it('falls back to built-in rendering when no templates are present', () => {
    const root = makeTempDir('ssg-tpl-');
    writeTree(root, {
      'content/a.md': `---
title: A
---
Body.`,
    });
    const outputDir = path.join(root, 'dist');

    build({
      contentDir: path.join(root, 'content'),
      outputDir,
      templateDir: path.join(root, 'missing-templates'),
    });

    const html = fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8');
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<title>A</title>');
    expect(html).toContain('<nav><a href="index.html">Home</a></nav>');
    expect(html).toContain('Body.');
  });

  it('exposes template, layout, and partial names', () => {
    const root = makeTempDir('ssg-tpl-');
    writeTree(root, {
      'templates/default.hbs': 'x',
      'templates/post.hbs': 'y',
      'templates/posts/post.hbs': 'z',
      'templates/layouts/default.hbs': 'w',
      'templates/partials/nav.hbs': 'n',
    });

    const engine = new TemplateEngine({ templateDir: path.join(root, 'templates') });

    expect(engine.active).toBe(true);
    expect(engine.getTemplateNames()).toContain('default');
    expect(engine.getTemplateNames()).toContain('post');
    expect(engine.getTemplateNames()).toContain('posts/post');
    expect(engine.getLayoutNames()).toContain('default');
    expect(engine.getPartialNames()).toContain('nav');
  });

  it('is inactive when the templates directory does not exist', () => {
    const root = makeTempDir('ssg-tpl-');
    const engine = new TemplateEngine({ templateDir: path.join(root, 'nope') });
    expect(engine.active).toBe(false);
  });
});
