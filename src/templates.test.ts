import fs from 'fs';
import path from 'path';
import { TemplateEngine, createTemplateEngine } from './templates';

const TEST_TEMPLATES_DIR = path.join(__dirname, '__test-templates');
const TEST_LAYOUTS_DIR = path.join(TEST_TEMPLATES_DIR, 'layouts');
const TEST_PARTIALS_DIR = path.join(TEST_TEMPLATES_DIR, 'partials');

function setupTestTemplateDir(): void {
  if (fs.existsSync(TEST_TEMPLATES_DIR)) {
    fs.rmSync(TEST_TEMPLATES_DIR, { recursive: true });
  }
  fs.mkdirSync(TEST_TEMPLATES_DIR, { recursive: true });
  fs.mkdirSync(TEST_LAYOUTS_DIR, { recursive: true });
  fs.mkdirSync(TEST_PARTIALS_DIR, { recursive: true });
}

function cleanupTestTemplateDir(): void {
  if (fs.existsSync(TEST_TEMPLATES_DIR)) {
    fs.rmSync(TEST_TEMPLATES_DIR, { recursive: true });
  }
}

describe('Template Engine', () => {
  beforeEach(setupTestTemplateDir);
  afterEach(cleanupTestTemplateDir);

  describe('Initialization', () => {
    it('should create engine with default config', () => {
      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      expect(engine).toBeDefined();
    });

    it('should create engine using factory function', () => {
      const engine = createTemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      expect(engine).toBeDefined();
    });

    it('should set default template directory', () => {
      const engine = createTemplateEngine();
      const path = engine.getTemplatePath('test');
      expect(path).toContain('templates');
    });
  });

  describe('Template Loading and Rendering', () => {
    it('should load and render simple template', () => {
      const templateContent = '<h1>{{title}}</h1><p>{{body}}</p>';
      fs.writeFileSync(
        path.join(TEST_TEMPLATES_DIR, 'page.hbs'),
        templateContent
      );

      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      const result = engine.renderTemplate('page', {
        title: 'Test Page',
        body: 'Test content',
      });

      expect(result).toContain('<h1>Test Page</h1>');
      expect(result).toContain('<p>Test content</p>');
    });

    it('should throw error for missing template', () => {
      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      expect(() => engine.loadTemplate('nonexistent')).toThrow(
        'Template not found'
      );
    });

    it('should cache loaded templates', () => {
      const templateContent = '<h1>{{title}}</h1>';
      fs.writeFileSync(
        path.join(TEST_TEMPLATES_DIR, 'cached.hbs'),
        templateContent
      );

      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      const template1 = engine.loadTemplate('cached');
      const template2 = engine.loadTemplate('cached');

      expect(template1).toBe(template2);
    });

    it('should render template with multiple variables', () => {
      const templateContent =
        '<h1>{{title}}</h1><p>{{content}}</p><span>{{author}}</span>';
      fs.writeFileSync(
        path.join(TEST_TEMPLATES_DIR, 'article.hbs'),
        templateContent
      );

      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      const result = engine.renderTemplate('article', {
        title: 'Article Title',
        content: 'Article content',
        author: 'John Doe',
      });

      expect(result).toContain('Article Title');
      expect(result).toContain('Article content');
      expect(result).toContain('John Doe');
    });

    it('should support Handlebars conditionals', () => {
      const templateContent =
        '{{#if published}}<p>This is published</p>{{else}}<p>Not published</p>{{/if}}';
      fs.writeFileSync(
        path.join(TEST_TEMPLATES_DIR, 'conditional.hbs'),
        templateContent
      );

      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      const publishedResult = engine.renderTemplate('conditional', {
        published: true,
      });
      expect(publishedResult).toContain('This is published');

      const unpublishedResult = engine.renderTemplate('conditional', {
        published: false,
      });
      expect(unpublishedResult).toContain('Not published');
    });

    it('should support Handlebars loops', () => {
      const templateContent =
        '<ul>{{#each items}}<li>{{this}}</li>{{/each}}</ul>';
      fs.writeFileSync(
        path.join(TEST_TEMPLATES_DIR, 'list.hbs'),
        templateContent
      );

      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      const result = engine.renderTemplate('list', {
        items: ['Item 1', 'Item 2', 'Item 3'],
      });

      expect(result).toContain('<li>Item 1</li>');
      expect(result).toContain('<li>Item 2</li>');
      expect(result).toContain('<li>Item 3</li>');
    });
  });

  describe('Layout Rendering', () => {
    it('should load and render layout', () => {
      const layoutContent =
        '<html><body>{{body}}</body></html>';
      fs.writeFileSync(
        path.join(TEST_LAYOUTS_DIR, 'default.hbs'),
        layoutContent
      );

      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      const result = engine.renderLayout('default', {});
      expect(result).toContain('<html>');
      expect(result).toContain('</html>');
    });

    it('should render page with layout', () => {
      const layoutContent =
        '<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>';
      fs.writeFileSync(
        path.join(TEST_LAYOUTS_DIR, 'html.hbs'),
        layoutContent
      );

      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      const pageContent = '<h1>Welcome</h1><p>Hello World</p>';
      const result = engine.renderPageWithLayout(
        pageContent,
        'html',
        { title: 'My Page' }
      );

      expect(result).toContain('<!DOCTYPE html>');
      expect(result).toContain('<title>My Page</title>');
      expect(result).toContain('<h1>Welcome</h1>');
      expect(result).toContain('<p>Hello World</p>');
    });

    it('should throw error for missing layout', () => {
      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      expect(() => engine.loadLayout('nonexistent')).toThrow(
        'Layout not found'
      );
    });

    it('should cache loaded layouts', () => {
      const layoutContent = '<html>{{{body}}}</html>';
      fs.writeFileSync(
        path.join(TEST_LAYOUTS_DIR, 'cached.hbs'),
        layoutContent
      );

      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      const layout1 = engine.loadLayout('cached');
      const layout2 = engine.loadLayout('cached');

      expect(layout1).toBe(layout2);
    });
  });

  describe('Partials', () => {
    it('should load and render partials', () => {
      const partialContent = '<footer>Copyright 2023</footer>';
      fs.writeFileSync(
        path.join(TEST_PARTIALS_DIR, 'footer.hbs'),
        partialContent
      );

      const templateContent = '<h1>{{title}}</h1>{{>footer}}';
      fs.writeFileSync(
        path.join(TEST_TEMPLATES_DIR, 'with-footer.hbs'),
        templateContent
      );

      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      const result = engine.renderTemplate('with-footer', {
        title: 'Page',
      });

      expect(result).toContain('<h1>Page</h1>');
      expect(result).toContain('<footer>Copyright 2023</footer>');
    });

    it('should load multiple partials', () => {
      const headerContent = '<header>My Site</header>';
      const footerContent = '<footer>Footer</footer>';
      const navContent = '<nav>Navigation</nav>';

      fs.writeFileSync(
        path.join(TEST_PARTIALS_DIR, 'header.hbs'),
        headerContent
      );
      fs.writeFileSync(
        path.join(TEST_PARTIALS_DIR, 'footer.hbs'),
        footerContent
      );
      fs.writeFileSync(
        path.join(TEST_PARTIALS_DIR, 'nav.hbs'),
        navContent
      );

      const templateContent =
        '{{>header}}{{>nav}}<main>Content</main>{{>footer}}';
      fs.writeFileSync(
        path.join(TEST_TEMPLATES_DIR, 'full-page.hbs'),
        templateContent
      );

      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      const result = engine.renderTemplate('full-page', {});

      expect(result).toContain('<header>My Site</header>');
      expect(result).toContain('<nav>Navigation</nav>');
      expect(result).toContain('<main>Content</main>');
      expect(result).toContain('<footer>Footer</footer>');
    });

    it('should handle missing partials directory gracefully', () => {
      const templateContent = '<h1>{{title}}</h1>';
      fs.writeFileSync(
        path.join(TEST_TEMPLATES_DIR, 'simple.hbs'),
        templateContent
      );

      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: '/nonexistent/partials',
      });

      const result = engine.renderTemplate('simple', { title: 'Test' });
      expect(result).toContain('<h1>Test</h1>');
    });

    it('should load partials only once', () => {
      const partialContent = '<span>Partial</span>';
      fs.writeFileSync(
        path.join(TEST_PARTIALS_DIR, 'reused.hbs'),
        partialContent
      );

      const templateContent =
        '{{>reused}}{{>reused}}{{>reused}}';
      fs.writeFileSync(
        path.join(TEST_TEMPLATES_DIR, 'repeat.hbs'),
        templateContent
      );

      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      const result = engine.renderTemplate('repeat', {});
      const count = (result.match(/<span>Partial<\/span>/g) || []).length;
      expect(count).toBe(3);
    });
  });

  describe('Helpers', () => {
    it('should register and use custom helpers', () => {
      const templateContent = '{{uppercase title}}';
      fs.writeFileSync(
        path.join(TEST_TEMPLATES_DIR, 'helper-test.hbs'),
        templateContent
      );

      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      engine.registerHelper('uppercase', (str: unknown) => {
        return String(str).toUpperCase();
      });

      const result = engine.renderTemplate('helper-test', {
        title: 'hello world',
      });

      expect(result).toContain('HELLO WORLD');
    });
  });

  describe('Path Utilities', () => {
    it('should generate template path', () => {
      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      const templatePath = engine.getTemplatePath('page');
      expect(templatePath).toBe(
        path.join(TEST_TEMPLATES_DIR, 'page.hbs')
      );
    });

    it('should generate layout path', () => {
      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      const layoutPath = engine.getLayoutPath('default');
      expect(layoutPath).toBe(
        path.join(TEST_LAYOUTS_DIR, 'default.hbs')
      );
    });
  });

  describe('Existence Checks', () => {
    it('should check template existence', () => {
      const templateContent = '<h1>Test</h1>';
      fs.writeFileSync(
        path.join(TEST_TEMPLATES_DIR, 'exists.hbs'),
        templateContent
      );

      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      expect(engine.hasTemplate('exists')).toBe(true);
      expect(engine.hasTemplate('does-not-exist')).toBe(false);
    });

    it('should check layout existence', () => {
      const layoutContent = '<html></html>';
      fs.writeFileSync(
        path.join(TEST_LAYOUTS_DIR, 'exists.hbs'),
        layoutContent
      );

      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      expect(engine.hasLayout('exists')).toBe(true);
      expect(engine.hasLayout('does-not-exist')).toBe(false);
    });
  });
});
