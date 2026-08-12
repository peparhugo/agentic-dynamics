export const DEFAULT_SERVE_PORT = 3000;
export const LIVE_RELOAD_PATH = '/__live_reload';

export const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html',
  '.htm': 'text/html',
  '.css': 'text/css',
  '.js': 'application/javascript',
  '.mjs': 'application/javascript',
  '.json': 'application/json',
  '.map': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain',
  '.xml': 'application/xml',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.otf': 'font/otf',
  '.pdf': 'application/pdf',
  '.md': 'text/markdown',
};

function liveReloadScript(): string {
  return `\n<script>
(function () {
  var ws;
  var retries = 0;
  function connect() {
    ws = new WebSocket('ws://' + location.host + '${LIVE_RELOAD_PATH}');
    ws.onmessage = function (event) {
      if (event.data === 'reload') {
        location.reload();
      }
    };
    ws.onclose = function () {
      if (retries < 60) {
        retries += 1;
        setTimeout(connect, 500);
      }
    };
    ws.onopen = function () {
      retries = 0;
    };
  }
  connect();
})();
</script>`;
}

export function injectLiveReload(html: string): string {
  const script = liveReloadScript();
  if (/<\/body>/i.test(html)) {
    return html.replace(/<\/body>/i, `${script}\n</body>`);
  }
  if (/<\/html>/i.test(html)) {
    return html.replace(/<\/html>/i, `${script}\n</html>`);
  }
  return html + script;
}
