import fs from 'fs';
import path from 'path';
import os from 'os';
import { TemplateEngine, createDefaultLayout, createDefaultIndexLayout, createDefaultNavPartial } from './template';

describe('TemplateEngine', () => {
  let tempDir: string;
  let templatesDir: string;
  let layoutsDir: string;
  let partialsDir: string;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-template-test-'));
    templatesDir = path.join(tempDir, 'templates');
    layoutsDir = path.join(tempDir, 'templates', 'layouts');
    partialsDir = path.join(tempDir, 'templates', 'partials');

    fs.mkdirSync(templatesDir, { recursive: true });
    fs.mkdirSync(layoutsDir, { recursive: true });
    fs.mkdirSync(partialsDir, { recursive: true });
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('creates template engine with directories', () => {
    const engine = new TemplateEngine({
      templatesDir,
      layoutsDir,
      partialsDir
    });

    expect(engine).toBeDefined();
  });

  it('renders template with data', () => {
    const templateContent = '<h1>{{title}}</h1>';
    fs.writeFileSync(path.join(templatesDir, 'test.hbs'), templateContent);

    const engine = new TemplateEngine({
      templatesDir,
      layoutsDir,
      partialsDir
    });

    const result = engine.render('test.hbs', undefined, { title: 'Hello' });
    expect(result).toContain('<h1>Hello</h1>');
  });

  it('renders template with layout', () => {
    const layoutContent = '<html><body>{{{body}}}</body></html>';
    fs.writeFileSync(path.join(layoutsDir, 'default.hbs'), layoutContent);

    const templateContent = '<h1>{{title}}</h1>';
    fs.writeFileSync(path.join(templatesDir, 'test.hbs'), templateContent);

    const engine = new TemplateEngine({
      templatesDir,
      layoutsDir,
      partialsDir
    });

    const result = engine.render('test.hbs', 'default.hbs', { title: 'Hello' });
    expect(result).toContain('<html><body>');
    expect(result).toContain('<h1>Hello</h1>');
    expect(result).toContain('</body></html>');
  });

  it('renders content with layout using renderWithLayout', () => {
    const layoutContent = '<html><body><header>Header</header>{{{body}}}<footer>Footer</footer></body></html>';
    fs.writeFileSync(path.join(layoutsDir, 'page.hbs'), layoutContent);

    const engine = new TemplateEngine({
      templatesDir,
      layoutsDir,
      partialsDir
    });

    const result = engine.renderWithLayout('<p>Content</p>', 'page.hbs', { title: 'Page' });
    expect(result).toContain('<header>Header</header>');
    expect(result).toContain('<p>Content</p>');
    expect(result).toContain('<footer>Footer</footer>');
  });

  it('returns content without layout if no layout specified', () => {
    const content = '<h1>Title</h1>';
    const engine = new TemplateEngine({
      templatesDir,
      layoutsDir,
      partialsDir
    });

    const result = engine.renderWithLayout(content, undefined, {});
    expect(result).toBe(content);
  });

  it('supports partials', () => {
    const navPartial = '<nav>Navigation</nav>';
    fs.writeFileSync(path.join(partialsDir, 'nav.hbs'), navPartial);

    const layoutContent = '<html><body>{{>nav}}{{{body}}}</body></html>';
    fs.writeFileSync(path.join(layoutsDir, 'default.hbs'), layoutContent);

    const templateContent = '<h1>{{title}}</h1>';
    fs.writeFileSync(path.join(templatesDir, 'test.hbs'), templateContent);

    const engine = new TemplateEngine({
      templatesDir,
      layoutsDir,
      partialsDir
    });

    const result = engine.render('test.hbs', 'default.hbs', { title: 'Hello' });
    expect(result).toContain('<nav>Navigation</nav>');
    expect(result).toContain('<h1>Hello</h1>');
  });

  it('handles conditional blocks in templates', () => {
    const templateContent = '{{#if date}}<p>{{date}}</p>{{/if}}';
    fs.writeFileSync(path.join(templatesDir, 'test.hbs'), templateContent);

    const engine = new TemplateEngine({
      templatesDir,
      layoutsDir,
      partialsDir
    });

    const resultWithDate = engine.render('test.hbs', undefined, { date: '2024-01-15' });
    expect(resultWithDate).toContain('<p>2024-01-15</p>');

    const resultWithoutDate = engine.render('test.hbs', undefined, {});
    expect(resultWithoutDate).not.toContain('<p>');
  });

  it('handles loops in templates', () => {
    const templateContent = '<ul>{{#each items}}<li>{{this}}</li>{{/each}}</ul>';
    fs.writeFileSync(path.join(templatesDir, 'test.hbs'), templateContent);

    const engine = new TemplateEngine({
      templatesDir,
      layoutsDir,
      partialsDir
    });

    const result = engine.render('test.hbs', undefined, { items: ['a', 'b', 'c'] });
    expect(result).toContain('<li>a</li>');
    expect(result).toContain('<li>b</li>');
    expect(result).toContain('<li>c</li>');
  });

  it('throws error when template not found', () => {
    const engine = new TemplateEngine({
      templatesDir,
      layoutsDir,
      partialsDir
    });

    expect(() => {
      engine.render('nonexistent.hbs', undefined, {});
    }).toThrow('Template not found');
  });

  it('uses cached templates on subsequent renders', () => {
    const templateContent = '<h1>{{title}}</h1>';
    fs.writeFileSync(path.join(templatesDir, 'test.hbs'), templateContent);

    const engine = new TemplateEngine({
      templatesDir,
      layoutsDir,
      partialsDir
    });

    const result1 = engine.render('test.hbs', undefined, { title: 'First' });
    const result2 = engine.render('test.hbs', undefined, { title: 'Second' });

    expect(result1).toContain('First');
    expect(result2).toContain('Second');
  });
});

describe('default template creators', () => {
  it('creates default layout', () => {
    const layout = createDefaultLayout();
    expect(layout).toContain('<!DOCTYPE html>');
    expect(layout).toContain('{{title}}');
    expect(layout).toContain('{{{body}}}');
    expect(layout).toContain('{{>nav}}');
  });

  it('creates default index layout', () => {
    const layout = createDefaultIndexLayout();
    expect(layout).toContain('<!DOCTYPE html>');
    expect(layout).toContain('{{#each pages}}');
    expect(layout).toContain('{{slug}}');
    expect(layout).toContain('{{title}}');
  });

  it('creates default nav partial', () => {
    const nav = createDefaultNavPartial();
    expect(nav).toContain('<nav>');
    expect(nav).toContain('href="index.html"');
    expect(nav).toContain('Home');
  });
});
