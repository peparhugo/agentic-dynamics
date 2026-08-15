import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { run } from '../src/cli';

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function writeFile(filePath: string, content: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content, 'utf8');
}

describe('ssg build --config', () => {
  let contentDir: string;
  let outputDir: string;
  let templatesDir: string;
  let configDir: string;
  let logSpy: jest.SpyInstance;

  beforeEach(() => {
    contentDir = makeTempDir('ssg-cli-config-content-');
    outputDir = makeTempDir('ssg-cli-config-output-');
    templatesDir = makeTempDir('ssg-cli-config-templates-');
    configDir = makeTempDir('ssg-cli-config-dir-');

    writeFile(
      path.join(contentDir, 'hello.md'),
      `---
title: Hello Config
---
Hello from a custom plugin pipeline.
`
    );

    writeFile(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '<html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>'
    );

    logSpy = jest.spyOn(console, 'log').mockImplementation(() => undefined);
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
    fs.rmSync(templatesDir, { recursive: true, force: true });
    fs.rmSync(configDir, { recursive: true, force: true });
    logSpy.mockRestore();
  });

  it('builds using the plugin pipeline declared in a custom config file', () => {
    const markdownPluginPath = path
      .join(__dirname, '..', 'plugins', 'markdown')
      .replace(/\\/g, '/');
    const templatePluginPath = path
      .join(__dirname, '..', 'plugins', 'template')
      .replace(/\\/g, '/');

    const configPath = path.join(configDir, 'ssg.config.js');
    writeFile(
      configPath,
      `
      const { MarkdownPlugin } = require(${JSON.stringify(markdownPluginPath)});
      const { TemplatePlugin } = require(${JSON.stringify(templatePluginPath)});

      const markedPlugin = {
        name: 'title-marker',
        onFile(page) {
          return { ...page, title: page.title + ' [via config]' };
        },
      };

      module.exports = {
        plugins: [new MarkdownPlugin(), markedPlugin, new TemplatePlugin()],
      };
      `
    );

    run([
      'node',
      'ssg',
      'build',
      '--content',
      contentDir,
      '--output',
      outputDir,
      '--templates',
      templatesDir,
      '--config',
      configPath,
    ]);

    const pageHtml = fs.readFileSync(path.join(outputDir, 'hello.html'), 'utf8');
    expect(pageHtml).toContain('Hello Config [via config]');
    expect(logSpy).toHaveBeenCalledWith(expect.stringContaining('Built 1 page(s)'));
  });

  it('falls back to the built-in plugins when the config file has no plugins', () => {
    const configPath = path.join(configDir, 'ssg.config.js');
    writeFile(configPath, `module.exports = {};`);

    run([
      'node',
      'ssg',
      'build',
      '--content',
      contentDir,
      '--output',
      outputDir,
      '--templates',
      templatesDir,
      '--config',
      configPath,
    ]);

    const pageHtml = fs.readFileSync(path.join(outputDir, 'hello.html'), 'utf8');
    expect(pageHtml).toContain('Hello Config');
    expect(pageHtml).not.toContain('[via config]');
  });
});
