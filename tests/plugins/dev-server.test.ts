import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import WebSocket from 'ws';
import { DevServerPlugin } from '../../plugins/dev-server';
import type { PluginContext } from '../../src/plugin';
import type { DevServerHandle } from '../../plugins/dev-server';

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function waitForOpen(socket: WebSocket): Promise<void> {
  return new Promise((resolve, reject) => {
    socket.once('open', () => resolve());
    socket.once('error', reject);
  });
}

function waitForMessage(socket: WebSocket): Promise<string> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Timed out waiting for message')), 5000);
    socket.once('message', (data) => {
      clearTimeout(timer);
      resolve(data.toString());
    });
  });
}

describe('DevServerPlugin', () => {
  let outputDir: string;
  let handle: DevServerHandle | undefined;

  beforeEach(() => {
    outputDir = makeTempDir('ssg-dev-server-plugin-');
    fs.writeFileSync(path.join(outputDir, 'index.html'), '<html><body>hi</body></html>');
  });

  afterEach(async () => {
    if (handle) {
      await handle.close();
      handle = undefined;
    }
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  it('broadcasts a reload message to connected clients when its afterBuild hook runs', async () => {
    const plugin = new DevServerPlugin();
    handle = await plugin.start({
      outputDir,
      watchPaths: [outputDir],
      port: 0,
      debounceMs: 20,
      rebuild: () => undefined,
    });

    const socket = new WebSocket(`ws://localhost:${handle.port}/__livereload`);
    await waitForOpen(socket);

    const reloadPromise = waitForMessage(socket);
    const ctx: PluginContext = { contentDir: '/unused', outputDir, templatesDir: '/unused', config: {} };
    plugin.afterBuild([], ctx);

    expect(await reloadPromise).toBe('reload');
    socket.close();
  });

  it('does not broadcast to clients that already disconnected', async () => {
    const plugin = new DevServerPlugin();
    handle = await plugin.start({
      outputDir,
      watchPaths: [outputDir],
      port: 0,
      debounceMs: 20,
      rebuild: () => undefined,
    });

    const socket = new WebSocket(`ws://localhost:${handle.port}/__livereload`);
    await waitForOpen(socket);
    socket.close();
    await new Promise((resolve) => setTimeout(resolve, 50));

    const ctx: PluginContext = { contentDir: '/unused', outputDir, templatesDir: '/unused', config: {} };
    expect(() => plugin.afterBuild([], ctx)).not.toThrow();
  });
});
