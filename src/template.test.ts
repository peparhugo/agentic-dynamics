import { promises as fs } from 'fs';
import path from 'path';
import {
  createTemplateEngine,
  loadPartials,
  loadTemplate,
  loadLayout,
  getEngine
} from './template';

const testDir = path.join(__dirname, '..', '__test_templates__');

async function cleanup(): Promise<void> {
  try {
    await fs.rm(testDir, { recursive: true, force: true });
  } catch (e) {
    // ignored
  }
}

async function setupTemplateDir(): Promise<void> {
  await fs.mkdir(path.join(testDir, 'layouts'), { recursive: true });
  await fs.mkdir(path.join(testDir, 'partials'), { recursive: true });
}

describe('template engine', () => {
  beforeEach(async () => {
    await cleanup();
    await setupTemplateDir();
  });

  afterEach(async () => {
    await cleanup();
  });

  describe('createTemplateEngine', () => {
    it('should create a template engine', () => {
      const engine = createTemplateEngine();
      expect(engine).toBeDefined();
      expect(engine.render).toBeDefined();
      expect(engine.registerPartial).toBeDefined();
    });

    it('should render simple templates', () => {
      const engine = createTemplateEngine();
      const result = engine.render('Hello {{name}}', { name: 'World' });
      expect(result).toBe('Hello World');
    });

    it('should support conditionals', () => {
      const engine = createTemplateEngine();
      const result = engine.render(
        '{{#if show}}Visible{{/if}}',
        { show: true }
      );
      expect(result).toContain('Visible');
    });

    it('should support loops', () => {
      const engine = createTemplateEngine();
      const result = engine.render(
        '{{#each items}}<li>{{this}}</li>{{/each}}',
        { items: ['a', 'b', 'c'] }
      );
      expect(result).toContain('<li>a</li>');
      expect(result).toContain('<li>b</li>');
      expect(result).toContain('<li>c</li>');
    });

    it('should register and use partials', () => {
      const engine = createTemplateEngine();
      engine.registerPartial('greet', 'Hello {{name}}!');
      const result = engine.render('{{>greet}}', { name: 'Alice' });
      expect(result).toBe('Hello Alice!');
    });

    it('should escape HTML by default', () => {
      const engine = createTemplateEngine();
      const result = engine.render('{{html}}', { html: '<script>alert("xss")</script>' });
      expect(result).toContain('&lt;script&gt;');
      expect(result).not.toContain('<script>');
    });

    it('should allow unescaped HTML with triple braces', () => {
      const engine = createTemplateEngine();
      const result = engine.render('{{{html}}}', { html: '<p>Safe HTML</p>' });
      expect(result).toContain('<p>Safe HTML</p>');
    });
  });

  describe('loadPartials', () => {
    it('should load partial templates from directory', async () => {
      await fs.writeFile(
        path.join(testDir, 'partials', 'header.hbs'),
        '<header>{{title}}</header>'
      );

      const engine = getEngine();
      await loadPartials(testDir);
      const result = engine.render('{{>header}}', { title: 'My Site' });
      expect(result).toContain('<header>My Site</header>');
    });

    it('should load multiple partials', async () => {
      await fs.writeFile(
        path.join(testDir, 'partials', 'header.hbs'),
        '<header>Header</header>'
      );
      await fs.writeFile(
        path.join(testDir, 'partials', 'footer.hbs'),
        '<footer>Footer</footer>'
      );

      const engine = getEngine();
      await loadPartials(testDir);
      const result = engine.render('{{>header}}{{>footer}}', {});
      expect(result).toContain('<header>Header</header>');
      expect(result).toContain('<footer>Footer</footer>');
    });

    it('should handle missing partials directory gracefully', async () => {
      const engine = getEngine();
      // Should not throw
      await loadPartials(testDir);
    });
  });

  describe('loadTemplate', () => {
    it('should load template from file', async () => {
      const templateContent = '<div>{{body}}</div>';
      await fs.writeFile(path.join(testDir, 'test.hbs'), templateContent);

      const content = await loadTemplate('test', testDir);
      expect(content).toBe(templateContent);
    });

    it('should load template from layouts directory', async () => {
      const layoutContent = '<html>{{{body}}}</html>';
      await fs.writeFile(
        path.join(testDir, 'layouts', 'test.hbs'),
        layoutContent
      );

      const content = await loadTemplate('test', testDir);
      expect(content).toBe(layoutContent);
    });

    it('should throw if template not found', async () => {
      await expect(loadTemplate('nonexistent', testDir)).rejects.toThrow();
    });
  });

  describe('loadLayout', () => {
    it('should load layout from layouts directory', async () => {
      const layoutContent = '<!DOCTYPE html>{{{body}}}</html>';
      await fs.writeFile(
        path.join(testDir, 'layouts', 'default.hbs'),
        layoutContent
      );

      const content = await loadLayout('default', testDir);
      expect(content).toBe(layoutContent);
    });

    it('should return default layout if not found', async () => {
      const content = await loadLayout('nonexistent', testDir);
      expect(content).toBe('{{body}}');
    });
  });
});
