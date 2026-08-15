import * as fs from 'fs';
import * as http from 'http';
import * as os from 'os';
import * as path from 'path';
import WebSocket from 'ws';
import { DevServerPlugin, injectLiveReload } from './dev-server-plugin';

function makeTmpDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function get(url: string): Promise<{ statusCode: number; body: string }> {
  return new Promise((resolve, reject) => {
    http
      .get(url, (res) => {
        let body = '';
        res.on('data', (chunk) => {
          body += chunk;
        });
        res.on('end', () => resolve({ statusCode: res.statusCode ?? 0, body }));
      })
      .on('error', reject);
  });
}

describe('DevServerPlugin', () => {
  let outputDir: string;
  let plugin: DevServerPlugin;

  beforeEach(() => {
    outputDir = makeTmpDir('ssg-devplugin-output-');
    fs.writeFileSync(path.join(outputDir, 'index.html'), '<html><body>Hi</body></html>');
    plugin = new DevServerPlugin(outputDir);
  });

  afterEach(async () => {
    await plugin.close();
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  it('is a no-op broadcast before listen() has been called', () => {
    expect(() => plugin.afterBuild([])).not.toThrow();
  });

  it('serves built files with live reload injected once listening', async () => {
    const { url } = await plugin.listen(0);

    const res = await get(url);
    expect(res.statusCode).toBe(200);
    expect(res.body).toContain('__livereload');
  });

  it('broadcasts "reload" to connected clients on afterBuild', async () => {
    const { port } = await plugin.listen(0);

    const ws = new WebSocket(`ws://localhost:${port}/__livereload`);
    await new Promise<void>((resolve, reject) => {
      ws.once('open', () => resolve());
      ws.once('error', reject);
    });

    const message = new Promise<string>((resolve) => {
      ws.once('message', (data) => resolve(data.toString()));
    });

    plugin.afterBuild([]);

    expect(await message).toBe('reload');
    ws.close();
  });
});

describe('injectLiveReload', () => {
  it('injects the reload script before </body>', () => {
    const result = injectLiveReload('<html><body>Hi</body></html>');
    expect(result).toContain('__livereload');
    expect(result.indexOf('<script>')).toBeLessThan(result.indexOf('</body>'));
  });
});
