import { existsSync, readFileSync } from 'fs';
import { join } from 'path';
import { buildSite } from '../src/build';
import { loadTemplates } from '../src/engine';
import { createFixture, cleanupFixture, Fixture } from './helpers';

describe('template engine', () => {
  let fixture: Fixture;

  afterEach(() => {
    cleanupFixture(fixture);
  });

  it('renders a page through a layout with a {{{body}}} placeholder', () => {
    fixture = createFixture(
      { 'post.md': '---\ntitle: First Post\n---\n\nHello **world**.' },
      {
        'layouts/default.hbs':
          '<html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>',
      }
    );

    buildSite(fixture.contentDir, fixture.outputDir, fixture.templatesDir);

    const html = readFileSync(join(fixture.outputDir, 'post.html'), 'utf8');
    expect(html).toContain('<title>First Post</title>');
    expect(html).toContain('<strong>world</strong>');
    expect(html).toContain('</body>');
  });

  it('injects reusable partials into a page', () => {
    fixture = createFixture(
      { 'post.md': '---\ntitle: First Post\n---\n\nBody.' },
      {
        'default.hbs': '{{> header}}<main>{{{content}}}</main>{{> footer}}',
        'partials/header.hbs': '<header>Site Header</header>',
        'partials/footer.hbs': '<footer>Site Footer</footer>',
      }
    );

    buildSite(fixture.contentDir, fixture.outputDir, fixture.templatesDir);

    const html = readFileSync(join(fixture.outputDir, 'post.html'), 'utf8');
    expect(html).toContain('<header>Site Header</header>');
    expect(html).toContain('<footer>Site Footer</footer>');
    expect(html).toContain('Body.');
  });

  it('uses the default page template when the page specifies none', () => {
    fixture = createFixture(
      { 'a.md': '# Heading' },
      { 'default.hbs': '<div class="default-tpl">{{{content}}}</div>' }
    );

    buildSite(fixture.contentDir, fixture.outputDir, fixture.templatesDir);

    const html = readFileSync(join(fixture.outputDir, 'a.html'), 'utf8');
    expect(html).toContain('<div class="default-tpl">');
    expect(html).toContain('<h1>Heading</h1>');
  });

  it('uses a page template named in frontmatter', () => {
    fixture = createFixture(
      { 'post.md': '---\ntitle: Post\ntemplate: post\n---\n\nBody.' },
      { 'post.hbs': '<article class="post">{{{content}}}</article>' }
    );

    buildSite(fixture.contentDir, fixture.outputDir, fixture.templatesDir);

    const html = readFileSync(join(fixture.outputDir, 'post.html'), 'utf8');
    expect(html).toContain('<article class="post">');
    expect(html).toContain('Body.');
  });

  it('uses a layout named in frontmatter', () => {
    fixture = createFixture(
      { 'post.md': '---\ntitle: Post\nlayout: wide\n---\n\nBody.' },
      { 'layouts/wide.hbs': '<div class="wide"><title>{{title}}</title>{{{body}}}</div>' }
    );

    buildSite(fixture.contentDir, fixture.outputDir, fixture.templatesDir);

    const html = readFileSync(join(fixture.outputDir, 'post.html'), 'utf8');
    expect(html).toContain('<div class="wide">');
    expect(html).toContain('<title>Post</title>');
    expect(html).toContain('Body.');
  });

  it('applies the default layout around the default page template', () => {
    fixture = createFixture(
      { 'post.md': '# Hi' },
      {
        'default.hbs': 'BODY:{{{content}}}',
        'layouts/default.hbs': 'WRAP[{{{body}}}]',
      }
    );

    buildSite(fixture.contentDir, fixture.outputDir, fixture.templatesDir);

    const html = readFileSync(join(fixture.outputDir, 'post.html'), 'utf8');
    expect(html).toContain('WRAP[BODY:<h1>Hi</h1>');
  });

  it('renders the index listing through an index template and layout', () => {
    fixture = createFixture(
      {
        'one.md': '---\ntitle: One\ndate: 2024-01-01\n---\n\nOne.',
        'two.md': '---\ntitle: Two\ndate: 2024-02-01\n---\n\nTwo.',
      },
      {
        'index.hbs': '<ul class="pages">{{#each pages}}<li><a href="{{slug}}.html">{{title}}</a></li>{{/each}}</ul>',
        'layouts/default.hbs': '<html><title>Home</title><main>{{{body}}}</main></html>',
      }
    );

    buildSite(fixture.contentDir, fixture.outputDir, fixture.templatesDir);

    const index = readFileSync(join(fixture.outputDir, 'index.html'), 'utf8');
    expect(index).toContain('href="one.html"');
    expect(index).toContain('href="two.html"');
    expect(index).toContain('>One</a>');
    expect(index).toContain('>Two</a>');
  });

  it('supports EJS templates with partials', () => {
    fixture = createFixture(
      { 'post.md': '---\ntitle: EJS Post\n---\n\nBody **ejs**.' },
      {
        'default.ejs': '<div class="ejs-page"><%- include("partials/title") %> <%- content %></div>',
        'partials/title.ejs': '<em><%= title %></em>',
      }
    );

    buildSite(fixture.contentDir, fixture.outputDir, fixture.templatesDir);

    const html = readFileSync(join(fixture.outputDir, 'post.html'), 'utf8');
    expect(html).toContain('<div class="ejs-page">');
    expect(html).toContain('<em>EJS Post</em>');
    expect(html).toContain('<strong>ejs</strong>');
  });

  it('falls back to built-in HTML when no templates directory exists', () => {
    fixture = createFixture({ 'post.md': '---\ntitle: Post\n---\n\nBody.' });

    buildSite(fixture.contentDir, fixture.outputDir, join(fixture.root, 'missing-templates'));

    const html = readFileSync(join(fixture.outputDir, 'post.html'), 'utf8');
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<title>Post</title>');
    expect(existsSync(join(fixture.outputDir, 'index.html'))).toBe(true);
  });

  it('loadTemplates returns null for a missing directory and an engine otherwise', () => {
    fixture = createFixture({ 'a.md': '# A' });

    expect(loadTemplates(join(fixture.root, 'missing'))).toBeNull();

    cleanupFixture(fixture);
    fixture = createFixture({ 'a.md': '# A' }, { 'page.hbs': '{{{content}}}' });

    const engine = loadTemplates(fixture.templatesDir);
    expect(engine).not.toBeNull();
    expect(engine?.hasPageTemplate('page')).toBe(true);
  });
});
