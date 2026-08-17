import * as fs from 'fs';
import * as http from 'http';
import * as os from 'os';
import * as path from 'path';
import { startServer, injectLiveReloadScript } from '../src/server';

function tmpdir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-serve-test-'));
}

function get(url: string): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    http
      .get(url, { agent: false }, (res) => {
        let data = '';
        res.on('data', (chunk) => (data += chunk));
        res.on('end', () =>
          resolve({ status: res.statusCode ?? 0, body: data })
        );
      })
      .on('error', reject);
  });
}

describe('injectLiveReloadScript', () => {
  it('injects the script before the closing body tag', () => {
    const html = '<html><body><p>hi</p></body></html>';
    const result = injectLiveReloadScript(html);
    expect(result).toContain('new WebSocket(');
    expect(result).toContain('location.reload()');
    expect(result.indexOf('new WebSocket(')).toBeLessThan(
      result.indexOf('</body>')
    );
  });

  it('appends the script when there is no body tag', () => {
    const html = '<html><p>hi</p></html>';
    const result = injectLiveReloadScript(html);
    expect(result).toContain('new WebSocket(');
  });
});

describe('startServer', () => {
  it('serves built pages from the output directory with live reload injected', async () => {
    const root = tmpdir();
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    fs.mkdirSync(content, { recursive: true });
    fs.writeFileSync(
      path.join(content, 'hello.md'),
      '---\ntitle: Hello\n---\n# Hello world\n'
    );

    const devServer = startServer({
      contentDir: content,
      outputDir: output,
      port: 0,
    });

    await new Promise<void>((resolve) => {
      devServer.server.once('listening', () => resolve());
    });

    const address = devServer.server.address();
    expect(address).not.toBeNull();
    const port =
      typeof address === 'object' && address !== null ? address.port : 0;

    const index = await get(`http://127.0.0.1:${port}/`);
    expect(index.status).toBe(200);
    expect(index.body).toContain('new WebSocket(');

    const page = await get(`http://127.0.0.1:${port}/hello.html`);
    expect(page.status).toBe(200);
    expect(page.body).toContain('Hello world');

    await devServer.close();
  });

  it('returns 404 for missing files', async () => {
    const root = tmpdir();
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    fs.mkdirSync(content, { recursive: true });
    fs.writeFileSync(path.join(content, 'a.md'), '# A\n');

    const devServer = startServer({
      contentDir: content,
      outputDir: output,
      port: 0,
    });

    await new Promise<void>((resolve) => {
      devServer.server.once('listening', () => resolve());
    });

    const address = devServer.server.address();
    const port =
      typeof address === 'object' && address !== null ? address.port : 0;

    const missing = await get(`http://127.0.0.1:${port}/nope.html`);
    expect(missing.status).toBe(404);

    await devServer.close();
  });
});
