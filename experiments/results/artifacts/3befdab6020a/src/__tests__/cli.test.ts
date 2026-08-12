import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import os from 'os';

const CLI = path.resolve(__dirname, '../cli.ts');

function runCli(args: string): { stdout: string; stderr: string; status: number } {
  try {
    const stdout = execSync(`npx ts-node ${CLI} ${args}`, {
      encoding: 'utf-8',
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    return { stdout, stderr: '', status: 0 };
  } catch (e: any) {
    return {
      stdout: e.stdout?.toString() || '',
      stderr: e.stderr?.toString() || '',
      status: e.status || 1,
    };
  }
}

function writeFile(dir: string, name: string, content: string): void {
  fs.writeFileSync(path.join(dir, name), content, 'utf-8');
}

describe('CLI', () => {
  let tmpDir: string;
  let contentDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-cli-test-'));
    contentDir = path.join(tmpDir, 'content');
    fs.mkdirSync(contentDir);
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it('prints usage and exits with code 1 when no subcommand given', () => {
    const { stderr, status } = runCli('');
    expect(status).toBe(1);
    expect(stderr).toContain('Usage:');
  });

  it('generates site with default directories', () => {
    const defaultContent = path.resolve('./content');
    const defaultOutput = path.resolve('./dist');

    // Clean up in case they exist
    fs.rmSync(defaultContent, { recursive: true, force: true });
    fs.rmSync(defaultOutput, { recursive: true, force: true });

    fs.mkdirSync(defaultContent, { recursive: true });
    writeFile(defaultContent, 'hello.md', `---
title: Default Test
date: '2024-01-01'
tags: []
---
Default content.`);

    const { stdout, status } = runCli('build');
    expect(status).toBe(0);
    expect(stdout).toContain('Generated 1 page(s)');

    expect(fs.existsSync(path.join(defaultOutput, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(defaultOutput, 'hello.html'))).toBe(true);

    // Cleanup
    fs.rmSync(defaultContent, { recursive: true, force: true });
    fs.rmSync(defaultOutput, { recursive: true, force: true });
  });

  it('respects --content and --output flags', () => {
    const customContent = path.join(tmpDir, 'mycontent');
    const customOutput = path.join(tmpDir, 'myoutput');
    fs.mkdirSync(customContent);

    writeFile(customContent, 'page.md', `---
title: Custom
date: '2024-01-01'
tags: []
---
Custom content.`);

    const { stdout, status } = runCli(`build --content ${customContent} --output ${customOutput}`);
    expect(status).toBe(0);
    expect(stdout).toContain('Generated 1 page(s)');
    expect(fs.existsSync(path.join(customOutput, 'page.html'))).toBe(true);
  });

  it('generates index with links to all pages', () => {
    writeFile(contentDir, 'a.md', `---
title: Page A
date: '2024-01-01'
tags: []
---
Content A`);

    writeFile(contentDir, 'b.md', `---
title: Page B
date: '2024-01-01'
tags: []
---
Content B`);

    const output = path.join(tmpDir, 'dist');

    const { status } = runCli(`build --content ${contentDir} --output ${output}`);
    expect(status).toBe(0);

    const indexHtml = fs.readFileSync(path.join(output, 'index.html'), 'utf-8');
    expect(indexHtml).toContain('<a href="a.html">Page A</a>');
    expect(indexHtml).toContain('<a href="b.html">Page B</a>');
  });

  it('handles empty content directory', () => {
    const output = path.join(tmpDir, 'dist');

    const { stdout, status } = runCli(`build --content ${contentDir} --output ${output}`);
    expect(status).toBe(0);
    expect(stdout).toContain('Generated 0 page(s)');
    expect(fs.existsSync(path.join(output, 'index.html'))).toBe(true);
  });
});
