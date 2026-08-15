"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.LIVERELOAD_PATH = void 0;
exports.reloadClientScript = reloadClientScript;
exports.injectReloadScript = injectReloadScript;
exports.LIVERELOAD_PATH = '/__ssg_livereload';
/**
 * Browser-side client that connects to the live-reload WebSocket endpoint and
 * reloads the page when a `reload` message arrives.
 */
function reloadClientScript() {
    return `<script>
(function () {
  var reconnectDelay = 500;
  function connect() {
    var ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '${exports.LIVERELOAD_PATH}');
    ws.onmessage = function (event) {
      if (event.data === 'reload') {
        location.reload();
      }
    };
    ws.onopen = function () {
      reconnectDelay = 500;
    };
    ws.onclose = function () {
      setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, 10000);
    };
  }
  connect();
})();
</script>`;
}
/**
 * Inject the live-reload client script into an HTML document just before the
 * closing `</body>` tag.
 */
function injectReloadScript(html) {
    const bodyClose = html.lastIndexOf('</body>');
    if (bodyClose === -1) {
        return html + '\n' + reloadClientScript();
    }
    return (html.slice(0, bodyClose) + reloadClientScript() + '\n' + html.slice(bodyClose));
}
