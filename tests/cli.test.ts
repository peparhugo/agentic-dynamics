import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { run } from '../src/cli';

describe('CLI', () => {
  test('build accepts custom content and output directories', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-cli-'));
    const content = path.join(root, 'posts');
    const output = path.join(root, 'web');
    const stdout = jest.spyOn(process.stdout, 'write').mockImplementation(() => true);
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'post.md'), 'A post');

    try {
      await run(['build', '--content', content, '--output', output]);
      await expect(fs.readFile(path.join(output, 'post.html'), 'utf8')).resolves.toContain('<p>A post</p>');
      expect(stdout).toHaveBeenCalledWith('Generated 1 page.\n');
    } finally {
      stdout.mockRestore();
      await fs.rm(root, { recursive: true, force: true });
    }
  });

  test('rejects unsupported commands and invalid options', async () => {
    await expect(run([])).rejects.toThrow('Usage: ssg <build|serve>');
    await expect(run(['deploy'])).rejects.toThrow('Usage: ssg <build|serve>');
    await expect(run(['build', '--content'])).rejects.toThrow('Missing value for --content');
    await expect(run(['build', '--port', '80'])).rejects.toThrow('Unknown option: --port');
    await expect(run(['serve', '--port', '0'])).rejects.toThrow('Invalid port: 0');
    await expect(run(['serve', '--port', 'abc'])).rejects.toThrow('Invalid port: abc');
  });

  test('accepts a custom templates directory', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-cli-'));
    const content = path.join(root, 'posts');
    const output = path.join(root, 'web');
    const templates = path.join(root, 'views');
    const stdout = jest.spyOn(process.stdout, 'write').mockImplementation(() => true);
    await fs.mkdir(content);
    await fs.mkdir(templates);
    await fs.writeFile(path.join(content, 'post.md'), 'Custom');
    await fs.writeFile(path.join(templates, 'default.hbs'), '<main>{{{content}}}</main>');

    try {
      await run(['build', '--content', content, '--output', output, '--templates', templates]);
      await expect(fs.readFile(path.join(output, 'post.html'), 'utf8')).resolves.toBe('<main><p>Custom</p></main>');
    } finally {
      stdout.mockRestore();
      await fs.rm(root, { recursive: true, force: true });
    }
  });
});
