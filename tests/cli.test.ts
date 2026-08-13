import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { run } from '../src/cli';

describe('CLI', () => {
  it('builds using custom content and output directories', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-cli-'));
    const content = path.join(root, 'posts');
    const output = path.join(root, 'public');
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'post.md'), '# Post');
    const stdout = jest.spyOn(process.stdout, 'write').mockImplementation(() => true);

    try {
      await run(['build', '--content', content, '--output', output]);
      expect(await fs.readFile(path.join(output, 'post.html'), 'utf8')).toContain('<h1>Post</h1>');
      expect(stdout).toHaveBeenCalledWith('Generated 1 page.\n');
    } finally {
      stdout.mockRestore();
      await fs.rm(root, { recursive: true, force: true });
    }
  });

  it('rejects unsupported commands and incomplete options', async () => {
    await expect(run(['preview'])).rejects.toThrow('Usage: ssg <build|serve>');
    await expect(run(['build', '--content'])).rejects.toThrow('--content requires a directory');
    await expect(run(['build', '--port', '3001'])).rejects.toThrow('--port is only available for serve');
    await expect(run(['serve', '--port', 'invalid'])).rejects.toThrow('--port must be an integer');
  });

  it('accepts a custom templates directory', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-cli-'));
    const content = path.join(root, 'content');
    const output = path.join(root, 'output');
    const templates = path.join(root, 'views');
    await fs.mkdir(content);
    await fs.mkdir(templates);
    await fs.writeFile(path.join(content, 'post.md'), '# Post');
    await fs.writeFile(path.join(templates, 'default.hbs'), '<custom>{{{content}}}</custom>');
    const stdout = jest.spyOn(process.stdout, 'write').mockImplementation(() => true);

    try {
      await run(['build', '--content', content, '--output', output, '--templates', templates]);
      expect(await fs.readFile(path.join(output, 'post.html'), 'utf8')).toContain('<custom><h1>Post</h1>');
    } finally {
      stdout.mockRestore();
      await fs.rm(root, { recursive: true, force: true });
    }
  });

  it('reports incremental build statistics', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-cli-'));
    const content = path.join(root, 'content');
    const output = path.join(root, 'output');
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'post.md'), '# Post');
    const stdout = jest.spyOn(process.stdout, 'write').mockImplementation(() => true);

    try {
      await run(['build', '--content', content, '--output', output, '--incremental']);
      await run(['build', '--content', content, '--output', output, '--incremental']);
      expect(stdout).toHaveBeenLastCalledWith(expect.stringMatching(/^Built 0 pages, skipped 1, time saved \d+ms\.\n$/));
    } finally {
      stdout.mockRestore();
      await fs.rm(root, { recursive: true, force: true });
    }
  });
});
