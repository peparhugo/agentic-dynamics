import * as fs from 'fs';
import * as path from 'path';
import { createTemplateEngine, renderIndexWithTemplate, renderEmptyIndex, type TemplateData } from '../templates.js';

describe('Template Engine', () => {
  let testTemplatesDir: string;

  beforeEach(() => {
    testTemplatesDir = path.join('/tmp', `test-templates-${Date.now()}`);
    fs.mkdirSync(testTemplatesDir, { recursive: true });
  });

  afterEach(() => {
    if (fs.existsSync(testTemplatesDir)) {
      fs.rmSync(testTemplatesDir, { recursive: true });
    }
  });

  it('should create template directories if they do not exist', () => {
    createTemplateEngine(testTemplatesDir);

    expect(fs.existsSync(testTemplatesDir)).toBe(true);
    expect(fs.existsSync(path.join(testTemplatesDir, 'layouts'))).toBe(true);
    expect(fs.existsSync(path.join(testTemplatesDir, 'partials'))).toBe(true);
  });

  it('should render page with default template', () => {
    const engine = createTemplateEngine(testTemplatesDir);

    const data: TemplateData = {
      title: 'Test Page',
      slug: 'test',
      body: '<p>Test content</p>',
    };

    const result = engine.renderPage('default', data);
    expect(result).toContain('<h1>Test Page</h1>');
    expect(result).toContain('Test content');
  });

  it('should render layout with default template', () => {
    const engine = createTemplateEngine(testTemplatesDir);

    const data: TemplateData = {
      title: 'Test Page',
      slug: 'test',
      body: '<article>Page content</article>',
    };

    const result = engine.renderLayout('default', data);
    expect(result).toContain('<!DOCTYPE html>');
    expect(result).toContain('<title>Test Page</title>');
    expect(result).toContain('Page content');
  });

  it('should load custom page template from file', () => {
    const engine = createTemplateEngine(testTemplatesDir);

    const customTemplate = '<section><h2>{{title}}</h2>{{{body}}}</section>';
    fs.writeFileSync(path.join(testTemplatesDir, 'custom.hbs'), customTemplate);

    const data: TemplateData = {
      title: 'Custom Page',
      slug: 'custom',
      body: '<p>Custom content</p>',
    };

    const result = engine.renderPage('custom', data);
    expect(result).toContain('<section>');
    expect(result).toContain('<h2>Custom Page</h2>');
    expect(result).toContain('Custom content');
  });

  it('should load custom layout template from file', () => {
    const engine = createTemplateEngine(testTemplatesDir);

    const layoutsDir = path.join(testTemplatesDir, 'layouts');
    const customLayout = '<div class="wrapper">{{{body}}}</div>';
    fs.writeFileSync(path.join(layoutsDir, 'custom.hbs'), customLayout);

    const data: TemplateData = {
      title: 'Page',
      slug: 'page',
      body: '<article>Content</article>',
    };

    const result = engine.renderLayout('custom', data);
    expect(result).toContain('<div class="wrapper">');
    expect(result).toContain('Content');
  });

  it('should render page with date metadata', () => {
    const engine = createTemplateEngine(testTemplatesDir);

    const data: TemplateData = {
      title: 'Dated Post',
      slug: 'dated',
      body: '<p>Content</p>',
      date: '2024-08-15',
    };

    const result = engine.renderPage('default', data);
    expect(result).toContain('2024-08-15');
  });

  it('should render page with tags metadata', () => {
    const engine = createTemplateEngine(testTemplatesDir);

    const data: TemplateData = {
      title: 'Tagged Post',
      slug: 'tagged',
      body: '<p>Content</p>',
      tags: ['javascript', 'typescript'],
    };

    const result = engine.renderPage('default', data);
    expect(result).toContain('javascript');
    expect(result).toContain('typescript');
  });

  it('should register partials from partials directory', () => {
    const engine = createTemplateEngine(testTemplatesDir);

    const partialsDir = path.join(testTemplatesDir, 'partials');
    const headerPartial = '<header>{{title}}</header>';
    fs.writeFileSync(path.join(partialsDir, 'header.hbs'), headerPartial);

    const layoutsDir = path.join(testTemplatesDir, 'layouts');
    const layoutWithPartial = '{{>header}}<main>{{{body}}}</main>';
    fs.writeFileSync(path.join(layoutsDir, 'with-partial.hbs'), layoutWithPartial);

    const data: TemplateData = {
      title: 'Page Title',
      slug: 'page',
      body: '<p>Content</p>',
    };

    const result = engine.renderLayout('with-partial', data);
    expect(result).toContain('<header>Page Title</header>');
    expect(result).toContain('<main>');
  });

  it('should render index with multiple pages', () => {
    const pages: TemplateData[] = [
      { title: 'First Post', slug: 'first', body: '', date: '2024-08-15' },
      { title: 'Second Post', slug: 'second', body: '', date: '2024-08-14' },
    ];

    const result = renderIndexWithTemplate(testTemplatesDir, pages);
    expect(result).toContain('first.html');
    expect(result).toContain('second.html');
    expect(result).toContain('First Post');
    expect(result).toContain('Second Post');
  });

  it('should render empty index when no pages', () => {
    const result = renderEmptyIndex(testTemplatesDir);
    expect(result).toContain('No pages found');
  });

  it('should support custom index layout', () => {
    const layoutsDir = path.join(testTemplatesDir, 'layouts');
    fs.mkdirSync(layoutsDir, { recursive: true });
    const customIndexLayout = '<div class="posts">{{#each pages}}<span>{{this.title}}</span>{{/each}}</div>';
    fs.writeFileSync(path.join(layoutsDir, 'index.hbs'), customIndexLayout);

    const pages: TemplateData[] = [
      { title: 'Post 1', slug: 'post1', body: '' },
      { title: 'Post 2', slug: 'post2', body: '' },
    ];

    const result = renderIndexWithTemplate(testTemplatesDir, pages);
    expect(result).toContain('<div class="posts">');
    expect(result).toContain('Post 1');
    expect(result).toContain('Post 2');
  });

  it('should handle handlebars conditionals', () => {
    const engine = createTemplateEngine(testTemplatesDir);

    const conditionalTemplate = `<article>
{{#if date}}<time>{{date}}</time>{{/if}}
{{{body}}}
</article>`;

    fs.writeFileSync(path.join(testTemplatesDir, 'conditional.hbs'), conditionalTemplate);

    const dataWithDate: TemplateData = {
      title: 'With Date',
      slug: 'with-date',
      body: '<p>Content</p>',
      date: '2024-08-15',
    };

    const dataWithoutDate: TemplateData = {
      title: 'Without Date',
      slug: 'without-date',
      body: '<p>Content</p>',
    };

    const resultWithDate = engine.renderPage('conditional', dataWithDate);
    const resultWithoutDate = engine.renderPage('conditional', dataWithoutDate);

    expect(resultWithDate).toContain('<time>2024-08-15</time>');
    expect(resultWithoutDate).not.toContain('<time>');
  });

  it('should handle handlebars loops', () => {
    const engine = createTemplateEngine(testTemplatesDir);

    const loopTemplate = `<ul>
{{#each tags}}<li>{{this}}</li>
{{/each}}</ul>
{{{body}}}`;

    fs.writeFileSync(path.join(testTemplatesDir, 'loop.hbs'), loopTemplate);

    const data: TemplateData = {
      title: 'Tagged',
      slug: 'tagged',
      body: '<p>Content</p>',
      tags: ['tag1', 'tag2', 'tag3'],
    };

    const result = engine.renderPage('loop', data);
    expect(result).toContain('<li>tag1</li>');
    expect(result).toContain('<li>tag2</li>');
    expect(result).toContain('<li>tag3</li>');
  });

  it('should load .html files as templates', () => {
    const engine = createTemplateEngine(testTemplatesDir);

    const htmlTemplate = '<div>{{title}}</div><div>{{{body}}}</div>';
    fs.writeFileSync(path.join(testTemplatesDir, 'html-template.html'), htmlTemplate);

    const data: TemplateData = {
      title: 'HTML Template',
      slug: 'html',
      body: '<p>Content</p>',
    };

    const result = engine.renderPage('html-template', data);
    expect(result).toContain('<div>HTML Template</div>');
    expect(result).toContain('Content');
  });

  it('should handle body placeholder in layout', () => {
    const engine = createTemplateEngine(testTemplatesDir);

    const layoutsDir = path.join(testTemplatesDir, 'layouts');
    const layout = `<!DOCTYPE html>
<html>
<body>
<div id="page">
{{{body}}}
</div>
</body>
</html>`;

    fs.writeFileSync(path.join(layoutsDir, 'with-body.hbs'), layout);

    const data: TemplateData = {
      title: 'Page',
      slug: 'page',
      body: '<h1>Content Title</h1><p>Content</p>',
    };

    const result = engine.renderLayout('with-body', data);
    expect(result).toContain('<div id="page">');
    expect(result).toContain('<h1>Content Title</h1>');
  });

  it('should escape HTML in title but not in body', () => {
    const engine = createTemplateEngine(testTemplatesDir);

    const data: TemplateData = {
      title: 'Title with <script>',
      slug: 'test',
      body: '<p>Safe HTML content</p>',
    };

    const result = engine.renderPage('default', data);
    expect(result).toContain('&lt;script&gt;');
    expect(result).toContain('<p>Safe HTML content</p>');
  });

  it('should support nested partials', () => {
    const engine = createTemplateEngine(testTemplatesDir);

    const partialsDir = path.join(testTemplatesDir, 'partials');
    const headerPartial = '<header>Site Header</header>';
    const navPartial = '<nav>{{>header}}</nav>';

    fs.writeFileSync(path.join(partialsDir, 'header.hbs'), headerPartial);
    fs.writeFileSync(path.join(partialsDir, 'nav.hbs'), navPartial);

    const layoutsDir = path.join(testTemplatesDir, 'layouts');
    const layoutWithNav = '{{>nav}}<main>{{{body}}}</main>';
    fs.writeFileSync(path.join(layoutsDir, 'with-nav.hbs'), layoutWithNav);

    const data: TemplateData = {
      title: 'Page',
      slug: 'page',
      body: '<article>Content</article>',
    };

    const result = engine.renderLayout('with-nav', data);
    expect(result).toContain('Site Header');
    expect(result).toContain('<nav>');
  });
});
