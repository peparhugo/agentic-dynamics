import fs from 'fs';
import os from 'os';
import path from 'path';
import { build, parseMarkdown, renderPageWithTemplates } from '../src/ssg';
import { loadTemplates, renderTemplateFile } from '../src/templates';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-tpl-'));
}

describe('parseMarkdown template frontmatter', () => {
  it('reads template and layout from frontmatter', () => {
    const raw = `<!--
title: X
template: post
layout: base
-->
Body`;
    const page = parseMarkdown(raw, 'x');
    expect(page.template).toBe('post');
    expect(page.layout).toBe('base');
    expect(page.data.template).toBe('post');
    expect(page.data.layout).toBe('base');
  });

  it('leaves template and layout undefined when absent', () => {
    const page = parseMarkdown('<!--\ntitle: X\n-->\nBody', 'x');
    expect(page.template).toBeUndefined();
    expect(page.layout).toBeUndefined();
  });
});

describe('loadTemplates', () => {
  it('loads templates, layouts, and partials from the expected directories', () => {
    const dir = makeTempDir();
    try {
      fs.mkdirSync(path.join(dir, 'layouts'));
      fs.mkdirSync(path.join(dir, 'partials'));
      fs.writeFileSync(path.join(dir, 'page.hbs'), '<h1>{{title}}</h1>');
      fs.writeFileSync(path.join(dir, 'layouts', 'default.hbs'), '<html>{{{body}}}</html>');
      fs.writeFileSync(path.join(dir, 'partials', 'header.hbs'), '<header>H</header>');
      fs.writeFileSync(path.join(dir, 'partials', 'nav.hbs'), '<nav>N</nav>');
      fs.writeFileSync(path.join(dir, 'partials', 'footer.hbs'), '<footer>F</footer>');
      fs.writeFileSync(path.join(dir, 'ignored.txt'), 'nope');

      const set = loadTemplates(dir);
      expect(set.templates.has('page')).toBe(true);
      expect(set.layouts.has('default')).toBe(true);
      expect(set.partials.has('header')).toBe(true);
      expect(set.partials.has('nav')).toBe(true);
      expect(set.partials.has('footer')).toBe(true);
      expect(set.templates.has('ignored')).toBe(false);
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });

  it('returns an empty set for a missing directory', () => {
    const set = loadTemplates(path.join(os.tmpdir(), 'no-templates-dir-xyz'));
    expect(set.templates.size).toBe(0);
    expect(set.layouts.size).toBe(0);
    expect(set.partials.size).toBe(0);
  });
});

describe('renderTemplateFile', () => {
  it('renders a Handlebars template with partials', () => {
    const dir = makeTempDir();
    try {
      const set = loadTemplates(dir);
      const html = renderTemplateFile(
        { name: 'page', engine: 'handlebars', source: '{{> header}}{{title}}', absPath: path.join(dir, 'page.hbs') },
        { title: 'Hi' },
        [
          { name: 'header', engine: 'handlebars', source: '<header>H</header>', absPath: '' },
        ]
      );
      expect(html).toBe('<header>H</header>Hi');
      expect(set).toBeDefined();
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });

  it('renders an EJS template with unescaped HTML', () => {
    const dir = makeTempDir();
    try {
      const html = renderTemplateFile(
        { name: 'page', engine: 'ejs', source: '<h1><%= title %></h1><%- html %>', absPath: path.join(dir, 'page.ejs') },
        { title: 'Hi', html: '<p>Body</p>' }
      );
      expect(html).toContain('<h1>Hi</h1>');
      expect(html).toContain('<p>Body</p>');
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });
});

describe('renderPageWithTemplates (Handlebars)', () => {
  function makeSet(files: Record<string, string>): string {
    const dir = makeTempDir();
    fs.mkdirSync(path.join(dir, 'layouts'), { recursive: true });
    fs.mkdirSync(path.join(dir, 'partials'), { recursive: true });
    for (const [rel, source] of Object.entries(files)) {
      const target = path.join(dir, rel);
      fs.mkdirSync(path.dirname(target), { recursive: true });
      fs.writeFileSync(target, source);
    }
    return dir;
  }

  it('wraps page content in the default layout with a {{{body}}} placeholder', () => {
    const dir = makeSet({
      'default.hbs': '{{> header}}<article><h1>{{title}}</h1>{{{html}}}</article>{{> footer}}',
      'layouts/default.hbs': '<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>',
      'partials/header.hbs': '<header>Site Header</header>',
      'partials/footer.hbs': '<footer>Site Footer</footer>',
    });
    const templates = loadTemplates(dir);
    const page = parseMarkdown('<!--\ntitle: Hello\n-->\n# Hello world', 'hello');
    const html = renderPageWithTemplates(page, templates);

    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<title>Hello</title>');
    expect(html).toContain('<header>Site Header</header>');
    expect(html).toContain('<footer>Site Footer</footer>');
    expect(html).toContain('<h1>Hello</h1>');
    expect(html).toContain('<h1>Hello world</h1>');
  });

  it('uses the template named in frontmatter', () => {
    const dir = makeSet({
      'default.hbs': 'DEFAULT {{title}}',
      'special.hbs': 'SPECIAL {{title}}',
    });
    const templates = loadTemplates(dir);
    const page = parseMarkdown('<!--\ntitle: P\ntemplate: special\n-->\nBody', 'p');
    const html = renderPageWithTemplates(page, templates);
    expect(html).toContain('SPECIAL P');
    expect(html).not.toContain('DEFAULT');
  });

  it('uses the layout named in frontmatter', () => {
    const dir = makeSet({
      'default.hbs': 'CONTENT {{title}}',
      'layouts/default.hbs': 'DEFAULT-LAYOUT {{{body}}}',
      'layouts/wide.hbs': 'WIDE-LAYOUT {{{body}}}',
    });
    const templates = loadTemplates(dir);
    const page = parseMarkdown('<!--\ntitle: P\nlayout: wide\n-->\nBody', 'p');
    const html = renderPageWithTemplates(page, templates);
    expect(html).toContain('WIDE-LAYOUT CONTENT P');
  });

  it('renders the template directly when no layout exists', () => {
    const dir = makeSet({ 'default.hbs': 'NO-LAYOUT {{title}}' });
    const templates = loadTemplates(dir);
    const page = parseMarkdown('<!--\ntitle: P\n-->\nBody', 'p');
    const html = renderPageWithTemplates(page, templates);
    expect(html).toBe('NO-LAYOUT P');
  });

  it('throws when frontmatter names a missing template', () => {
    const dir = makeSet({ 'default.hbs': 'DEFAULT {{title}}' });
    const templates = loadTemplates(dir);
    const page = parseMarkdown('<!--\ntitle: P\ntemplate: nope\n-->\nBody', 'p');
    expect(() => renderPageWithTemplates(page, templates)).toThrow(/Template not found: nope/);
  });

  it('throws when frontmatter names a missing layout', () => {
    const dir = makeSet({
      'default.hbs': 'CONTENT {{title}}',
      'layouts/default.hbs': 'DEFAULT {{{body}}}',
    });
    const templates = loadTemplates(dir);
    const page = parseMarkdown('<!--\ntitle: P\nlayout: nope\n-->\nBody', 'p');
    expect(() => renderPageWithTemplates(page, templates)).toThrow(/Layout not found: nope/);
  });

  it('falls back to the legacy renderer when no default template exists', () => {
    const dir = makeSet({ 'layouts/default.hbs': '{{{body}}}' });
    const templates = loadTemplates(dir);
    const page = parseMarkdown('<!--\ntitle: P\n-->\n# P', 'p');
    const html = renderPageWithTemplates(page, templates);
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<title>P</title>');
  });
});

describe('build with templates', () => {
  it('generates templated pages with layouts and partials for Handlebars', () => {
    const content = makeTempDir();
    const output = makeTempDir();
    const templates = makeTempDir();
    try {
      fs.mkdirSync(path.join(templates, 'layouts'));
      fs.mkdirSync(path.join(templates, 'partials'));
      fs.writeFileSync(
        path.join(templates, 'default.hbs'),
        '{{> header}}{{> nav}}\n<article><h1>{{title}}</h1>{{{html}}}</article>\n{{> footer}}'
      );
      fs.writeFileSync(
        path.join(templates, 'layouts', 'default.hbs'),
        '<!DOCTYPE html><html lang="en"><head><title>{{title}}</title></head><body>{{{body}}}</body></html>'
      );
      fs.writeFileSync(path.join(templates, 'partials', 'header.hbs'), '<header>HDR</header>');
      fs.writeFileSync(path.join(templates, 'partials', 'nav.hbs'), '<nav>NAV</nav>');
      fs.writeFileSync(path.join(templates, 'partials', 'footer.hbs'), '<footer>FTR</footer>');
      fs.writeFileSync(path.join(content, 'hello.md'), '<!--\ntitle: Hello\ndate: 2024-05-10\ntags: [news]\n-->\n# Hello world');

      const pages = build(content, output, templates);
      expect(pages.map((p) => p.slug)).toEqual(['hello']);

      const html = fs.readFileSync(path.join(output, 'hello.html'), 'utf8');
      expect(html).toContain('<!DOCTYPE html>');
      expect(html).toContain('<title>Hello</title>');
      expect(html).toContain('<header>HDR</header>');
      expect(html).toContain('<nav>NAV</nav>');
      expect(html).toContain('<footer>FTR</footer>');
      expect(html).toContain('<h1>Hello</h1>');
      expect(html).toContain('<h1>Hello world</h1>');
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(output, { recursive: true, force: true });
      fs.rmSync(templates, { recursive: true, force: true });
    }
  });

  it('generates templated pages for EJS with includes', () => {
    const content = makeTempDir();
    const output = makeTempDir();
    const templates = makeTempDir();
    try {
      fs.mkdirSync(path.join(templates, 'layouts'));
      fs.mkdirSync(path.join(templates, 'partials'));
      fs.writeFileSync(
        path.join(templates, 'default.ejs'),
        `<%- include('partials/header') %>\n<article><h1><%= title %></h1><%- html %></article>\n<%- include('partials/footer') %>`
      );
      fs.writeFileSync(
        path.join(templates, 'layouts', 'default.ejs'),
        '<!DOCTYPE html><html><head><title><%= title %></title></head><body>{{{body}}}</body></html>'
      );
      fs.writeFileSync(path.join(templates, 'partials', 'header.ejs'), '<header>EJS HDR</header>');
      fs.writeFileSync(path.join(templates, 'partials', 'footer.ejs'), '<footer>EJS FTR</footer>');
      fs.writeFileSync(path.join(content, 'hello.md'), '<!--\ntitle: Hello\n-->\n# Hello world');

      build(content, output, templates);

      const html = fs.readFileSync(path.join(output, 'hello.html'), 'utf8');
      expect(html).toContain('<!DOCTYPE html>');
      expect(html).toContain('<title>Hello</title>');
      expect(html).toContain('<header>EJS HDR</header>');
      expect(html).toContain('<footer>EJS FTR</footer>');
      expect(html).toContain('<h1>Hello</h1>');
      expect(html).toContain('<h1>Hello world</h1>');
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(output, { recursive: true, force: true });
      fs.rmSync(templates, { recursive: true, force: true });
    }
  });

  it('renders the index page through an index template', () => {
    const content = makeTempDir();
    const output = makeTempDir();
    const templates = makeTempDir();
    try {
      fs.mkdirSync(path.join(templates, 'layouts'));
      fs.writeFileSync(
        path.join(templates, 'index.hbs'),
        '<ul>{{#each pages}}<li><a href="{{slug}}.html">{{title}}</a></li>{{/each}}</ul>'
      );
      fs.writeFileSync(
        path.join(templates, 'layouts', 'default.hbs'),
        '<!DOCTYPE html><html><body>{{{body}}}</body></html>'
      );
      fs.writeFileSync(path.join(content, 'alpha.md'), '<!--\ntitle: Alpha\n-->\n# A');
      fs.writeFileSync(path.join(content, 'beta.md'), '<!--\ntitle: Beta\ndate: 2024-01-01\n-->\n# B');

      build(content, output, templates);

      const indexHtml = fs.readFileSync(path.join(output, 'index.html'), 'utf8');
      expect(indexHtml).toContain('<a href="alpha.html">Alpha</a>');
      expect(indexHtml).toContain('<a href="beta.html">Beta</a>');
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(output, { recursive: true, force: true });
      fs.rmSync(templates, { recursive: true, force: true });
    }
  });

  it('falls back to legacy rendering when no templates directory exists', () => {
    const content = makeTempDir();
    const output = makeTempDir();
    const missing = path.join(os.tmpdir(), `ssg-no-templates-${Date.now()}`);
    try {
      fs.writeFileSync(path.join(content, 'a.md'), '<!--\ntitle: A\n-->\n# A');

      build(content, output, missing);

      const html = fs.readFileSync(path.join(output, 'a.html'), 'utf8');
      expect(html).toContain('<!DOCTYPE html>');
      expect(html).toContain('<title>A</title>');

      const indexHtml = fs.readFileSync(path.join(output, 'index.html'), 'utf8');
      expect(indexHtml).toContain('<a href="a.html">A</a>');
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(output, { recursive: true, force: true });
      fs.rmSync(missing, { recursive: true, force: true });
    }
  });
});
