import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { Page } from '../src/page';
import { PluginContext } from '../src/plugin';
import { templatePlugin } from './template-plugin';

function makeTmpDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

describe('templatePlugin', () => {
  let outputDir: string;
  let templatesDir: string;
  let ctx: PluginContext;

  beforeEach(() => {
    outputDir = makeTmpDir('ssg-tpl-plugin-output-');
    templatesDir = makeTmpDir('ssg-tpl-plugin-templates-');
    fs.mkdirSync(path.join(templatesDir, 'layouts'));
    ctx = { contentDir: outputDir, outputDir, templatesDir, config: {} };
  });

  afterEach(() => {
    fs.rmSync(outputDir, { recursive: true, force: true });
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  it('renders each page through its template/layout and writes it to disk', () => {
    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), '<h1>{{title}}</h1>{{{html}}}');
    fs.writeFileSync(path.join(templatesDir, 'layouts', 'default.hbs'), '<body>{{{body}}}</body>');

    const page: Page = {
      slug: 'hello',
      title: 'Hello',
      date: null,
      tags: [],
      html: '<p>Hi</p>',
      sourcePath: '/dev/null',
      outputPath: 'hello.html',
      template: 'page',
      layout: 'default',
    };

    const plugin = templatePlugin();
    plugin.beforeBuild!(ctx);
    plugin.onFile!(page, ctx);

    const written = fs.readFileSync(path.join(outputDir, 'hello.html'), 'utf-8');
    expect(written).toBe('<body><h1>Hello</h1><p>Hi</p></body>');
  });

  it('writes an index.html listing all pages in afterBuild', () => {
    fs.writeFileSync(path.join(templatesDir, 'index.hbs'), 'INDEX:{{#each pages}}{{title}};{{/each}}');
    fs.writeFileSync(path.join(templatesDir, 'layouts', 'default.hbs'), '{{{body}}}');

    const pages: Page[] = [
      {
        slug: 'a',
        title: 'A',
        date: null,
        tags: [],
        html: '',
        sourcePath: '/dev/null',
        outputPath: 'a.html',
        template: 'page',
        layout: 'default',
      },
    ];

    const plugin = templatePlugin();
    plugin.beforeBuild!(ctx);
    plugin.afterBuild!(pages, ctx);

    const written = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(written).toBe('INDEX:A;');
  });

  it('creates the output directory in beforeBuild', () => {
    fs.rmSync(outputDir, { recursive: true, force: true });
    expect(fs.existsSync(outputDir)).toBe(false);

    templatePlugin().beforeBuild!(ctx);

    expect(fs.existsSync(outputDir)).toBe(true);
  });
});
