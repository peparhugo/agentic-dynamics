import type { Page, Plugin, PluginContext } from '../types';

export const LIVE_RELOAD_SCRIPT_ID = 'ssg-live-reload';

export const WS_PATH = '/live-reload';

export function liveReloadScript(port: number): string {
  return `<script id="${LIVE_RELOAD_SCRIPT_ID}">
(function () {
  var port = ${port};
  function connect() {
    var proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    var ws = new WebSocket(proto + '//' + location.hostname + ':' + port + '${WS_PATH}');
    ws.onmessage = function () { location.reload(); };
    ws.onclose = function () { setTimeout(connect, 1000); };
    ws.onerror = function () { ws.close(); };
  }
  connect();
})();
</script>`;
}

export function injectLiveReload(html: string, port: number): string {
  const script = liveReloadScript(port);
  if (/<\/body>/i.test(html)) {
    return html.replace(/<\/body>/i, `${script}\n</body>`);
  }
  return `${html}\n${script}`;
}

export class DevServerPlugin implements Plugin {
  readonly name = 'dev-server';

  liveReloadScript(port: number): string {
    return liveReloadScript(port);
  }

  injectLiveReload(html: string, port: number): string {
    return injectLiveReload(html, port);
  }

  onStart(_ctx: PluginContext): void {}

  beforeBuild(_ctx: PluginContext): void {}

  afterBuild(_ctx: PluginContext): void {}

  onFile(_page: Page, _ctx: PluginContext): void {}

  onEnd(_ctx: PluginContext): void {}
}
