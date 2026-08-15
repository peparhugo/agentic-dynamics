import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { TemplateEngine } from '../src/template-engine';

describe('TemplateEngine', () => {
  let tempDir: string;
  let templatesDir: string;
  let layoutsDir: string;
  let partialsDir: string;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-templates-'));
    templatesDir = path.join(tempDir, 'templates');
    layoutsDir = path.join(templatesDir, 'layouts');
    partialsDir = path.join(templatesDir, 'partials');
    fs.mkdirSync(templatesDir);
    fs.mkdirSync(layoutsDir);
    fs.mkdirSync(partialsDir);
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('should render a simple template', () => {
    const templateContent = '<h1>{{title}}</h1><p>{{content}}</p>';
    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), templateContent);

    const engine = new TemplateEngine(templatesDir);
    const result = engine.renderTemplate(path.join(templatesDir, 'page.hbs'), {
      title: 'Test Page',
      content: 'Hello World',
    });

    expect(result).toContain('<h1>Test Page</h1>');
    expect(result).toContain('<p>Hello World</p>');
  });

  it('should cache compiled templates', () => {
    const templateContent = '<div>{{message}}</div>';
    fs.writeFileSync(path.join(templatesDir, 'simple.hbs'), templateContent);

    const engine = new TemplateEngine(templatesDir);
    const templatePath = path.join(templatesDir, 'simple.hbs');

    const result1 = engine.renderTemplate(templatePath, { message: 'First' });
    const result2 = engine.renderTemplate(templatePath, { message: 'Second' });

    expect(result1).toContain('<div>First</div>');
    expect(result2).toContain('<div>Second</div>');
  });

  it('should support layouts with body placeholder', () => {
    const layoutContent = '<html><body>{{{body}}}</body></html>';
    fs.writeFileSync(path.join(layoutsDir, 'default.hbs'), layoutContent);

    const templateContent = '<h1>{{title}}</h1>';
    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), templateContent);

    const engine = new TemplateEngine(templatesDir);
    const result = engine.renderPageTemplate('page', { title: 'My Page' }, 'default');

    expect(result).toContain('<html>');
    expect(result).toContain('<body>');
    expect(result).toContain('<h1>My Page</h1>');
    expect(result).toContain('</body>');
    expect(result).toContain('</html>');
  });

  it('should register and use partials', () => {
    const headerPartial = '<header>{{siteName}}</header>';
    const footerPartial = '<footer>Copyright 2024</footer>';
    fs.writeFileSync(path.join(partialsDir, 'header.hbs'), headerPartial);
    fs.writeFileSync(path.join(partialsDir, 'footer.hbs'), footerPartial);

    const layoutContent = '{{>header}}<main>{{{body}}}</main>{{>footer}}';
    fs.writeFileSync(path.join(layoutsDir, 'default.hbs'), layoutContent);

    const templateContent = '<h1>{{title}}</h1>';
    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), templateContent);

    const engine = new TemplateEngine(templatesDir);
    const result = engine.renderPageTemplate(
      'page',
      { title: 'Test', siteName: 'My Site' },
      'default'
    );

    expect(result).toContain('<header>My Site</header>');
    expect(result).toContain('<h1>Test</h1>');
    expect(result).toContain('<footer>Copyright 2024</footer>');
  });

  it('should check if layout exists', () => {
    fs.writeFileSync(path.join(layoutsDir, 'blog.hbs'), '<html>{{body}}</html>');

    const engine = new TemplateEngine(templatesDir);
    expect(engine.hasLayout('blog')).toBe(true);
    expect(engine.hasLayout('nonexistent')).toBe(false);
  });

  it('should list available templates', () => {
    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), '<div>page</div>');
    fs.writeFileSync(path.join(templatesDir, 'post.hbs'), '<div>post</div>');

    const engine = new TemplateEngine(templatesDir);
    const templates = engine.getAvailableTemplates();

    expect(templates).toContain('page');
    expect(templates).toContain('post');
  });

  it('should list available layouts', () => {
    fs.writeFileSync(path.join(layoutsDir, 'default.hbs'), '<html>{{body}}</html>');
    fs.writeFileSync(path.join(layoutsDir, 'blog.hbs'), '<html>{{body}}</html>');

    const engine = new TemplateEngine(templatesDir);
    const layouts = engine.getAvailableLayouts();

    expect(layouts).toContain('default');
    expect(layouts).toContain('blog');
  });

  it('should throw error for missing template', () => {
    const engine = new TemplateEngine(templatesDir);
    const missingPath = path.join(templatesDir, 'missing.hbs');

    expect(() => {
      engine.renderTemplate(missingPath, {});
    }).toThrow('Template not found');
  });

  it('should handle missing partials directory gracefully', () => {
    const templatesWithoutPartials = path.join(tempDir, 'empty-templates');
    fs.mkdirSync(templatesWithoutPartials);
    fs.mkdirSync(path.join(templatesWithoutPartials, 'layouts'));

    const layoutContent = '<html>{{body}}</html>';
    fs.writeFileSync(
      path.join(templatesWithoutPartials, 'layouts', 'default.hbs'),
      layoutContent
    );

    expect(() => {
      new TemplateEngine(templatesWithoutPartials);
    }).not.toThrow();
  });

  it('should support nested data in templates', () => {
    const templateContent = '<h1>{{meta.title}}</h1><p>Author: {{meta.author}}</p>';
    fs.writeFileSync(path.join(templatesDir, 'article.hbs'), templateContent);

    const engine = new TemplateEngine(templatesDir);
    const result = engine.renderTemplate(path.join(templatesDir, 'article.hbs'), {
      meta: {
        title: 'Article Title',
        author: 'John Doe',
      },
    });

    expect(result).toContain('<h1>Article Title</h1>');
    expect(result).toContain('<p>Author: John Doe</p>');
  });

  it('should support handlebars conditionals', () => {
    const templateContent = `
      <h1>{{title}}</h1>
      {{#if published}}
        <p>This post is published</p>
      {{else}}
        <p>This post is a draft</p>
      {{/if}}
    `;
    fs.writeFileSync(path.join(templatesDir, 'post.hbs'), templateContent);

    const engine = new TemplateEngine(templatesDir);
    const publishedResult = engine.renderTemplate(path.join(templatesDir, 'post.hbs'), {
      title: 'Published Post',
      published: true,
    });
    const draftResult = engine.renderTemplate(path.join(templatesDir, 'post.hbs'), {
      title: 'Draft Post',
      published: false,
    });

    expect(publishedResult).toContain('This post is published');
    expect(draftResult).toContain('This post is a draft');
  });

  it('should support handlebars loops', () => {
    const templateContent = `
      <ul>
      {{#each items}}
        <li>{{this}}</li>
      {{/each}}
      </ul>
    `;
    fs.writeFileSync(path.join(templatesDir, 'list.hbs'), templateContent);

    const engine = new TemplateEngine(templatesDir);
    const result = engine.renderTemplate(path.join(templatesDir, 'list.hbs'), {
      items: ['Apple', 'Banana', 'Cherry'],
    });

    expect(result).toContain('<li>Apple</li>');
    expect(result).toContain('<li>Banana</li>');
    expect(result).toContain('<li>Cherry</li>');
  });

  it('should render layout without template when template is not found', () => {
    const layoutContent = '<html><h1>{{title}}</h1>{{{body}}}</html>';
    fs.writeFileSync(path.join(layoutsDir, 'default.hbs'), layoutContent);

    const engine = new TemplateEngine(templatesDir);
    const result = engine.renderLayout('default', { title: 'Home', body: '<p>Content</p>' });

    expect(result).toContain('<html>');
    expect(result).toContain('<h1>Home</h1>');
    expect(result).toContain('<p>Content</p>');
  });
});
