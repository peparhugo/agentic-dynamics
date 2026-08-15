import fs from 'fs';
import os from 'os';
import path from 'path';
import { spawnSync } from 'child_process';

const CLI_ENTRY = path.join(__dirname, '..', 'src', 'cli.ts');
const TS_NODE_REGISTER = require.resolve('ts-node/register/transpile-only');

function makeTmpDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function runCli(args: string[], cwd: string) {
  return spawnSync(process.execPath, ['-r', TS_NODE_REGISTER, CLI_ENTRY, ...args], {
    cwd,
    encoding: 'utf-8',
    env: {
      ...process.env,
      TS_NODE_PROJECT: path.join(__dirname, '..', 'tsconfig.json'),
    },
  });
}

describe('ssg CLI', () => {
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    contentDir = makeTmpDir('ssg-cli-content-');
    outputDir = makeTmpDir('ssg-cli-dist-');
    fs.writeFileSync(
      path.join(contentDir, 'page.md'),
      `---
title: CLI Page
date: 2024-03-01
---
Hello from the CLI test.`
    );
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  it('builds the site using --content and --output flags', () => {
    const result = runCli(['build', '--content', contentDir, '--output', outputDir], process.cwd());

    expect(result.status).toBe(0);
    expect(result.stdout).toContain('Built 1 page(s)');
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'page.html'))).toBe(true);
    const pageHtml = fs.readFileSync(path.join(outputDir, 'page.html'), 'utf-8');
    expect(pageHtml).toContain('CLI Page');
  }, 20000);

  it('defaults to ./content and ./dist relative to the current working directory', () => {
    const workDir = makeTmpDir('ssg-cli-cwd-');
    fs.mkdirSync(path.join(workDir, 'content'));
    fs.writeFileSync(path.join(workDir, 'content', 'only.md'), '# Only Page');

    const result = runCli(['build'], workDir);

    expect(result.status).toBe(0);
    expect(fs.existsSync(path.join(workDir, 'dist', 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(workDir, 'dist', 'only.html'))).toBe(true);

    fs.rmSync(workDir, { recursive: true, force: true });
  }, 20000);

  it('exits with an error when the content directory is missing', () => {
    const result = runCli(['build', '--content', path.join(contentDir, 'missing'), '--output', outputDir], process.cwd());

    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain('Content directory not found');
  }, 20000);

  it('builds using a custom --templates directory and honors the per-page frontmatter template', () => {
    const templatesDir = makeTmpDir('ssg-cli-templates-');
    fs.mkdirSync(path.join(templatesDir, 'layouts'));
    fs.writeFileSync(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '<html><body class="default-layout">{{{body}}}</body></html>'
    );
    fs.writeFileSync(
      path.join(templatesDir, 'layouts', 'post.hbs'),
      '<html><body class="post-layout">{{{body}}}</body></html>'
    );
    fs.writeFileSync(
      path.join(contentDir, 'templated-page.md'),
      `---
title: Templated Page
template: post
---
Body content.`
    );

    const result = runCli(
      ['build', '--content', contentDir, '--output', outputDir, '--templates', templatesDir],
      process.cwd()
    );

    expect(result.status).toBe(0);
    const templatedHtml = fs.readFileSync(path.join(outputDir, 'templated-page.html'), 'utf-8');
    expect(templatedHtml).toContain('class="post-layout"');
    const pageHtml = fs.readFileSync(path.join(outputDir, 'page.html'), 'utf-8');
    expect(pageHtml).toContain('class="default-layout"');

    fs.rmSync(templatesDir, { recursive: true, force: true });
  }, 20000);
});
