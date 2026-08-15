import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { TemplatePlugin } from '../../plugins/template';
import type { PluginContext } from '../../src/plugin';
import type { Page } from '../../src/types';

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function writeFile(filePath: string, content: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content, 'utf8');
}

function page(overrides: Partial<Page> = {}): Page {
  return {
    slug: 'a',
    title: 'Page A',
    tags: [],
    html: '<p>hi</p>',
    sourcePath: 'a.md',
    outputFile: 'a.html',
    ...overrides,
  };
}

describe('TemplatePlugin', () => {
  let outputDir: string;
  let templatesDir: string;
  let ctx: PluginContext;

  beforeEach(() => {
    outputDir = makeTempDir('ssg-template-plugin-output-');
    templatesDir = makeTempDir('ssg-template-plugin-templates-');
    writeFile(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '<html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>'
    );
    ctx = { contentDir: '/unused', outputDir, templatesDir, config: {} };
  });

  afterEach(() => {
    fs.rmSync(outputDir, { recursive: true, force: true });
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  it('throws in beforeBuild when the templates directory is missing', () => {
    const plugin = new TemplatePlugin();
    expect(() =>
      plugin.beforeBuild({ ...ctx, templatesDir: path.join(templatesDir, 'nope') })
    ).toThrow();
  });

  it('throws if afterBuild runs before beforeBuild', () => {
    const plugin = new TemplatePlugin();
    expect(() => plugin.afterBuild([page()], ctx)).toThrow(/beforeBuild must run before afterBuild/);
  });

  it('writes a rendered HTML file per page and an index.html listing', () => {
    const plugin = new TemplatePlugin();
    plugin.beforeBuild(ctx);
    plugin.afterBuild([page({ title: 'First' }), page({ slug: 'b', outputFile: 'b.html', title: 'Second' })], ctx);

    const firstHtml = fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8');
    expect(firstHtml).toContain('<title>First</title>');
    expect(firstHtml).toContain('<p>hi</p>');

    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8');
    expect(indexHtml).toContain('href="a.html"');
    expect(indexHtml).toContain('href="b.html"');
    expect(indexHtml).toContain('First');
    expect(indexHtml).toContain('Second');
  });

  it('throws a clear error for an unknown layout', () => {
    const plugin = new TemplatePlugin();
    plugin.beforeBuild(ctx);
    expect(() => plugin.afterBuild([page({ layout: 'missing-layout' })], ctx)).toThrow(
      /missing-layout/
    );
  });
});
