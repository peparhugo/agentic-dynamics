import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { run } from '../src/cli';

describe('CLI', () => {
  let root: string;
  let writeSpy: jest.SpyInstance;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-cli-'));
    writeSpy = jest.spyOn(process.stdout, 'write').mockImplementation(() => true);
  });

  afterEach(async () => {
    writeSpy.mockRestore();
    await fs.rm(root, { recursive: true, force: true });
  });

  it('builds using custom content and output directories', async () => {
    const content = path.join(root, 'posts');
    const output = path.join(root, 'site');
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'post.md'), '# Post');

    await run(['build', '--content', content, '--output', output]);

    await expect(fs.access(path.join(output, 'post.html'))).resolves.toBeUndefined();
    expect(writeSpy).toHaveBeenCalledWith('Generated 1 page.\n');
  });

  it('builds using a custom templates directory', async () => {
    const content = path.join(root, 'posts');
    const output = path.join(root, 'site');
    const templates = path.join(root, 'views');
    await fs.mkdir(content);
    await fs.mkdir(templates);
    await fs.writeFile(path.join(content, 'post.md'), '# Post');
    await fs.writeFile(path.join(templates, 'default.hbs'), '<main>{{{body}}}</main>');

    await run(['build', '--content', content, '--output', output, '--templates', templates]);

    await expect(fs.readFile(path.join(output, 'post.html'), 'utf8')).resolves.toBe('<main><h1>Post</h1>\n</main>');
  });

  it.each([
    [[], 'Usage: ssg build'],
    [['serve'], 'Usage: ssg build'],
    [['build', '--unknown'], 'Unknown option: --unknown'],
    [['build', '--content'], 'Missing value for --content'],
  ])('rejects invalid arguments', async (arguments_, message) => {
    await expect(run(arguments_ as string[])).rejects.toThrow(message as string);
  });
});
