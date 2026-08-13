import fs from 'fs';
import path from 'path';
import { TemplateEngine } from '../template-engine';
import { ParsedPage } from '../parser';

describe('TemplateEngine', () => {
  const testDir = path.join(__dirname, '../..', '.test-templates');
  const templatesDir = path.join(testDir, 'templates');
  const layoutsDir = path.join(templatesDir, 'layouts');
  const partialsDir = path.join(templatesDir, 'partials');

  beforeEach(() => {
    if (fs.existsSync(testDir)) {
      fs.rmSync(testDir, { recursive: true });
    }
    fs.mkdirSync(partialsDir, { recursive: true });
    fs.mkdirSync(layoutsDir, { recursive: true });
  });

  afterEach(() => {
    if (fs.existsSync(testDir)) {
      fs.rmSync(testDir, { recursive: true });
    }
  });

  describe('renderPage without template or layout', () => {
    it('should render page html directly', () => {
      const engine = new TemplateEngine({ templateDir: templatesDir });
      const page: ParsedPage = {
        slug: 'test',
        frontmatter: {
          title: 'Test Page',
        },
        html: '<p>Test content</p>',
      };

      const result = engine.renderPage(page);

      expect(result).toBe('<p>Test content</p>');
    });
  });

  describe('renderPage with template', () => {
    it('should render with specified template', () => {
      fs.writeFileSync(path.join(templatesDir, 'post.hbs'), '<article><h2>{{title}}</h2>{{{body}}}</article>');

      const engine = new TemplateEngine({ templateDir: templatesDir });
      const page: ParsedPage = {
        slug: 'test-post',
        frontmatter: {
          title: 'My Post',
        },
        html: '<p>Post content</p>',
      };

      const result = engine.renderPage(page, 'post');

      expect(result).toContain('<article>');
      expect(result).toContain('<h2>My Post</h2>');
      expect(result).toContain('<p>Post content</p>');
      expect(result).toContain('</article>');
    });

    it('should throw error when template not found', () => {
      const engine = new TemplateEngine({ templateDir: templatesDir });
      const page: ParsedPage = {
        slug: 'test',
        frontmatter: {
          title: 'Test',
        },
        html: '<p>Content</p>',
      };

      expect(() => {
        engine.renderPage(page, 'nonexistent');
      }).toThrow('Template not found');
    });

    it('should access frontmatter properties in template', () => {
      fs.writeFileSync(
        path.join(templatesDir, 'blog.hbs'),
        '<div class="post"><h1>{{title}}</h1><p>By {{author}}</p>{{{body}}}</div>'
      );

      const engine = new TemplateEngine({ templateDir: templatesDir });
      const page: ParsedPage = {
        slug: 'article',
        frontmatter: {
          title: 'Article Title',
          author: 'John Doe',
        },
        html: '<p>Article body</p>',
      };

      const result = engine.renderPage(page, 'blog');

      expect(result).toContain('Article Title');
      expect(result).toContain('By John Doe');
      expect(result).toContain('Article body');
    });
  });

  describe('renderPage with layout', () => {
    it('should wrap template content with layout', () => {
      fs.writeFileSync(path.join(templatesDir, 'post.hbs'), '<article>{{{body}}}</article>');
      fs.writeFileSync(
        path.join(layoutsDir, 'default.hbs'),
        '<html><body>{{body}}</body></html>'
      );

      const engine = new TemplateEngine({ templateDir: templatesDir });
      const page: ParsedPage = {
        slug: 'test',
        frontmatter: {
          title: 'Test',
        },
        html: '<p>Content</p>',
      };

      const result = engine.renderPage(page, 'post', 'default');

      expect(result).toContain('<html>');
      expect(result).toContain('<body>');
      expect(result).toContain('<article>');
      expect(result).toContain('<p>Content</p>');
      expect(result).toContain('</article>');
      expect(result).toContain('</body>');
      expect(result).toContain('</html>');
    });

    it('should use layout without template', () => {
      fs.writeFileSync(
        path.join(layoutsDir, 'base.hbs'),
        '<html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>'
      );

      const engine = new TemplateEngine({ templateDir: templatesDir });
      const page: ParsedPage = {
        slug: 'page',
        frontmatter: {
          title: 'My Page',
        },
        html: '<h1>Welcome</h1>',
      };

      const result = engine.renderPage(page, undefined, 'base');

      expect(result).toContain('<title>My Page</title>');
      expect(result).toContain('<h1>Welcome</h1>');
      expect(result).toContain('<html>');
    });

    it('should throw error when layout not found', () => {
      const engine = new TemplateEngine({ templateDir: templatesDir });
      const page: ParsedPage = {
        slug: 'test',
        frontmatter: {
          title: 'Test',
        },
        html: '<p>Content</p>',
      };

      expect(() => {
        engine.renderPage(page, undefined, 'missing');
      }).toThrow('Template not found');
    });
  });

  describe('partials support', () => {
    it('should register and use header partial', () => {
      fs.writeFileSync(path.join(partialsDir, 'header.hbs'), '<header><h1>Site Header</h1></header>');
      fs.writeFileSync(
        path.join(layoutsDir, 'main.hbs'),
        '{{> header}}<main>{{{body}}}</main>'
      );

      const engine = new TemplateEngine({ templateDir: templatesDir });
      const page: ParsedPage = {
        slug: 'test',
        frontmatter: {
          title: 'Test',
        },
        html: '<p>Page content</p>',
      };

      const result = engine.renderPage(page, undefined, 'main');

      expect(result).toContain('<header>');
      expect(result).toContain('Site Header');
      expect(result).toContain('</header>');
      expect(result).toContain('<main>');
      expect(result).toContain('</main>');
    });

    it('should register and use footer partial', () => {
      fs.writeFileSync(path.join(partialsDir, 'footer.hbs'), '<footer><p>© 2024</p></footer>');
      fs.writeFileSync(
        path.join(layoutsDir, 'layout.hbs'),
        '<div>{{{body}}}{{> footer}}</div>'
      );

      const engine = new TemplateEngine({ templateDir: templatesDir });
      const page: ParsedPage = {
        slug: 'test',
        frontmatter: {
          title: 'Test',
        },
        html: '<p>Content</p>',
      };

      const result = engine.renderPage(page, undefined, 'layout');

      expect(result).toContain('<footer>');
      expect(result).toContain('© 2024');
      expect(result).toContain('</footer>');
    });

    it('should handle multiple partials', () => {
      fs.writeFileSync(path.join(partialsDir, 'nav.hbs'), '<nav>Navigation</nav>');
      fs.writeFileSync(path.join(partialsDir, 'footer.hbs'), '<footer>Footer</footer>');
      fs.writeFileSync(
        path.join(layoutsDir, 'full.hbs'),
        '{{> nav}}<main>{{{body}}}</main>{{> footer}}'
      );

      const engine = new TemplateEngine({ templateDir: templatesDir });
      const page: ParsedPage = {
        slug: 'test',
        frontmatter: {
          title: 'Test',
        },
        html: '<p>Content</p>',
      };

      const result = engine.renderPage(page, undefined, 'full');

      expect(result).toContain('<nav>');
      expect(result).toContain('Navigation');
      expect(result).toContain('</nav>');
      expect(result).toContain('<main>');
      expect(result).toContain('</main>');
      expect(result).toContain('<footer>');
      expect(result).toContain('Footer');
      expect(result).toContain('</footer>');
    });

    it('should handle partial directory not existing', () => {
      fs.mkdirSync(partialsDir, { recursive: true });
      fs.rmSync(partialsDir, { recursive: true });

      const engine = new TemplateEngine({ templateDir: templatesDir });
      fs.writeFileSync(path.join(templatesDir, 'simple.hbs'), '<p>{{{body}}}</p>');

      const page: ParsedPage = {
        slug: 'test',
        frontmatter: {
          title: 'Test',
        },
        html: '<p>Content</p>',
      };

      const result = engine.renderPage(page, 'simple');

      expect(result).toContain('<p>');
      expect(result).toContain('Content');
    });
  });

  describe('template caching', () => {
    it('should cache compiled templates', () => {
      fs.writeFileSync(path.join(templatesDir, 'post.hbs'), '<article>{{{body}}}</article>');

      const engine = new TemplateEngine({ templateDir: templatesDir });
      const page: ParsedPage = {
        slug: 'test',
        frontmatter: { title: 'Test' },
        html: '<p>Content</p>',
      };

      const result1 = engine.renderPage(page, 'post');
      const result2 = engine.renderPage(page, 'post');

      expect(result1).toBe(result2);
    });

    it('should cache compiled layouts', () => {
      fs.writeFileSync(path.join(layoutsDir, 'default.hbs'), '<html>{{{body}}}</html>');

      const engine = new TemplateEngine({ templateDir: templatesDir });
      const page: ParsedPage = {
        slug: 'test',
        frontmatter: { title: 'Test' },
        html: '<p>Content</p>',
      };

      const result1 = engine.renderPage(page, undefined, 'default');
      const result2 = engine.renderPage(page, undefined, 'default');

      expect(result1).toBe(result2);
    });
  });

  describe('hasTemplate and hasLayout', () => {
    it('should check if template exists', () => {
      fs.writeFileSync(path.join(templatesDir, 'post.hbs'), '<article>{{{body}}}</article>');

      const engine = new TemplateEngine({ templateDir: templatesDir });

      expect(engine.hasTemplate('post')).toBe(true);
      expect(engine.hasTemplate('missing')).toBe(false);
    });

    it('should check if layout exists', () => {
      fs.writeFileSync(path.join(layoutsDir, 'main.hbs'), '<html>{{{body}}}</html>');

      const engine = new TemplateEngine({ templateDir: templatesDir });

      expect(engine.hasLayout('main')).toBe(true);
      expect(engine.hasLayout('missing')).toBe(false);
    });
  });

  describe('handlebar expressions', () => {
    it('should handle conditional expressions', () => {
      fs.writeFileSync(
        path.join(templatesDir, 'conditional.hbs'),
        '{{#if date}}<p>Published: {{date}}</p>{{/if}}{{{body}}}'
      );

      const engine = new TemplateEngine({ templateDir: templatesDir });

      const pageWithDate: ParsedPage = {
        slug: 'test1',
        frontmatter: { title: 'Test', date: '2024-01-15' },
        html: '<p>Content</p>',
      };

      const pageWithoutDate: ParsedPage = {
        slug: 'test2',
        frontmatter: { title: 'Test' },
        html: '<p>Content</p>',
      };

      const result1 = engine.renderPage(pageWithDate, 'conditional');
      const result2 = engine.renderPage(pageWithoutDate, 'conditional');

      expect(result1).toContain('Published: 2024-01-15');
      expect(result2).not.toContain('Published:');
    });

    it('should handle loops', () => {
      fs.writeFileSync(
        path.join(templatesDir, 'tags.hbs'),
        '{{#each tags}}<span>{{this}}</span>{{/each}}{{{body}}}'
      );

      const engine = new TemplateEngine({ templateDir: templatesDir });
      const page: ParsedPage = {
        slug: 'test',
        frontmatter: { title: 'Test', tags: ['tag1', 'tag2', 'tag3'] },
        html: '<p>Content</p>',
      };

      const result = engine.renderPage(page, 'tags');

      expect(result).toContain('<span>tag1</span>');
      expect(result).toContain('<span>tag2</span>');
      expect(result).toContain('<span>tag3</span>');
    });
  });

  describe('safe HTML rendering', () => {
    it('should render raw HTML with triple braces', () => {
      fs.writeFileSync(path.join(templatesDir, 'raw.hbs'), '<div>{{{body}}}</div>');

      const engine = new TemplateEngine({ templateDir: templatesDir });
      const page: ParsedPage = {
        slug: 'test',
        frontmatter: { title: 'Test' },
        html: '<p>HTML content</p>',
      };

      const result = engine.renderPage(page, 'raw');

      expect(result).toContain('<p>HTML content</p>');
    });

    it('should escape text with double braces', () => {
      fs.writeFileSync(path.join(templatesDir, 'safe.hbs'), '<div>{{title}}</div>');

      const engine = new TemplateEngine({ templateDir: templatesDir });
      const page: ParsedPage = {
        slug: 'test',
        frontmatter: { title: '<script>alert("xss")</script>' },
        html: '<p>Content</p>',
      };

      const result = engine.renderPage(page, 'safe');

      expect(result).not.toContain('<script>');
      expect(result).toContain('&lt;script&gt;');
    });
  });
});
