import { promises as fs } from 'fs';
import os from 'os';
import path from 'path';
import http from 'http';
import WebSocket from 'ws';
import { serve, injectLiveReload, liveReloadScript } from '../src/serve';
import type { DevServer } from '../src/serve';

async function makeTempDir(): Promise<string> {
  return fs.mkdtemp(path.join(os.tmpdir(), 'ssg-serve-'));
}

function get(port: number, pathname: string): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    http
      .get({ host: 'localhost', port, path: pathname }, (res) => {
        let body = '';
        res.on('data', (chunk) => (body += chunk));
        res.on('end', () => resolve({ status: res.statusCode ?? 0, body }));
      })
      .on('error', reject);
  });
}

describe('live reload injection', () => {
  it('injects the script before </body>', () => {
    const html = '<html><body><h1>Hi</h1></body></html>';
    const out = injectLiveReload(html);
    expect(out).toContain('data-ssg-live-reload');
    expect(out).toContain('location.reload');
    expect(out.indexOf('<script')).toBeLessThan(out.indexOf('</body>'));
  });

  it('appends the script when there is no body tag', () => {
    const html = '<html><h1>Hi</h1></html>';
    const out = injectLiveReload(html);
    expect(out).toContain('data-ssg-live-reload');
  });

  it('produces a script that connects over WebSocket and reloads', () => {
    const script = liveReloadScript();
    expect(script).toContain('WebSocket');
    expect(script).toContain('reload');
  });
});

describe('serve', () => {
  let dev: DevServer;
  let contentDir: string;
  let outputDir: string;

  beforeAll(async () => {
    contentDir = await makeTempDir();
    outputDir = await makeTempDir();
    await fs.writeFile(
      path.join(contentDir, 'a.md'),
      '---\ntitle: Alpha\n---\n# First'
    );
    dev = await serve({ content: contentDir, output: outputDir, port: 0 });
  });

  afterAll(async () => {
    await dev.close();
  });

  it('serves built HTML with the live reload script injected', async () => {
    const index = await get(dev.port, '/');
    expect(index.status).toBe(200);
    expect(index.body).toContain('data-ssg-live-reload');

    const page = await get(dev.port, '/a.html');
    expect(page.status).toBe(200);
    expect(page.body).toContain('<h1>First</h1>');
    expect(page.body).toContain('location.reload');
  });

  it('rebuilds on content change and notifies websocket clients', async () => {
    const ws = new WebSocket(`ws://localhost:${dev.port}`);
    const reloaded = new Promise<boolean>((resolve) => {
      ws.on('message', (data) => resolve(data.toString() === 'reload'));
    });
    await new Promise<void>((resolve) => ws.on('open', () => resolve()));

    await fs.writeFile(
      path.join(contentDir, 'a.md'),
      '---\ntitle: Alpha\n---\n# Second'
    );

    const deadline = Date.now() + 5000;
    let body = '';
    while (Date.now() < deadline) {
      const page = await get(dev.port, '/a.html');
      body = page.body;
      if (body.includes('<h1>Second</h1>')) {
        break;
      }
      await new Promise((r) => setTimeout(r, 100));
    }

    expect(body).toContain('<h1>Second</h1>');
    expect(await reloaded).toBe(true);

    ws.close();
  });
});
