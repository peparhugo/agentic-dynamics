import { promises as fs } from 'node:fs';
import path from 'node:path';
import type { Plugin } from './plugin';

export interface DevServerPluginOptions {
  port: number;
}

const liveReloadScript = (port: number): string => `<script>
(function () {
  var socket = new WebSocket('ws://' + location.hostname + ':${port}');
  socket.onmessage = function (event) { if (event.data === 'reload') location.reload(); };
  socket.onclose = function () { setTimeout(function () { location.reload(); }, 1000); };
}());
</script>`;

export const injectLiveReload = (html: string, port: number): string => {
  const script = liveReloadScript(port);
  const closingBody = html.lastIndexOf('</body>');
  return closingBody >= 0 ? `${html.slice(0, closingBody)}${script}${html.slice(closingBody)}` : `${html}${script}`;
};

/** Adds the development client to generated HTML. The server handles websocket delivery. */
export const DevServerPlugin = (options: DevServerPluginOptions): Plugin => ({
  async afterBuild(context) {
    const outputDir = path.resolve(context.options.outputDir ?? './dist');
    const visit = async (directory: string): Promise<void> => {
      for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
        const file = path.join(directory, entry.name);
        if (entry.isDirectory()) await visit(file);
        else if (entry.isFile() && entry.name.endsWith('.html')) await fs.writeFile(file, injectLiveReload(await fs.readFile(file, 'utf8'), options.port));
      }
    };
    await visit(outputDir);
  },
});
