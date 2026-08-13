import { mkdir, mkdtemp, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { WebSocket } from 'ws';
import { serveSite } from '../src/server.js';

describe('serveSite', () => {
  it('serves rebuilt pages with a live reload client and notifies connected browsers', async () => {
    const root = await mkdtemp(path.join(os.tmpdir(), 'ssg-server-'));
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    await mkdir(content);
    await writeFile(path.join(content, 'hello.md'), '# Hello');
    const developmentServer = await serveSite({ contentDir: content, outputDir: output, port: 0 });
    const socket = new WebSocket(`ws://localhost:${developmentServer.port}`);
    await new Promise<void>((resolve) => socket.once('open', resolve));

    const response = await fetch(`http://localhost:${developmentServer.port}/hello.html`);
    expect(await response.text()).toContain('new WebSocket');

    const reloaded = new Promise<void>((resolve) => socket.once('message', () => resolve()));
    await writeFile(path.join(content, 'hello.md'), '# Updated');
    await reloaded;
    const closed = new Promise<void>((resolve) => socket.once('close', () => resolve()));
    socket.close();
    await closed;
    await developmentServer.close();
  });
});
