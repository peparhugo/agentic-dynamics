"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.LIVE_RELOAD_SCRIPT = exports.RELOAD_MESSAGE = void 0;
exports.injectLiveReloadScript = injectLiveReloadScript;
exports.startDevServer = startDevServer;
const fs_1 = __importDefault(require("fs"));
const http_1 = __importDefault(require("http"));
const path_1 = __importDefault(require("path"));
const chokidar_1 = require("chokidar");
const ws_1 = require("ws");
const index_1 = require("./index");
exports.RELOAD_MESSAGE = 'reload';
exports.LIVE_RELOAD_SCRIPT = `<script>
(function () {
  var socket = new WebSocket('ws://' + window.location.host);
  socket.addEventListener('message', function (event) {
    if (event.data === '${exports.RELOAD_MESSAGE}') {
      window.location.reload();
    }
  });
})();
</script>`;
const CONTENT_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.htm': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.ico': 'image/x-icon',
    '.txt': 'text/plain; charset=utf-8',
    '.md': 'text/markdown; charset=utf-8',
};
function injectLiveReloadScript(html, script = exports.LIVE_RELOAD_SCRIPT) {
    if (/<\/body>/i.test(html)) {
        return html.replace(/<\/body>/i, script + '\n</body>');
    }
    return html + '\n' + script;
}
function isHtml(filePath) {
    const ext = path_1.default.extname(filePath).toLowerCase();
    return ext === '.html' || ext === '.htm';
}
function contentTypeFor(filePath) {
    const ext = path_1.default.extname(filePath).toLowerCase();
    return CONTENT_TYPES[ext] ?? 'application/octet-stream';
}
function createRequestHandler(outputDir) {
    return (req, res) => {
        const rawPath = (req.url ?? '/').split('?')[0];
        let pathname;
        try {
            pathname = decodeURIComponent(rawPath);
        }
        catch {
            res.writeHead(400);
            res.end('Bad request');
            return;
        }
        const relative = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
        const filePath = path_1.default.resolve(outputDir, relative);
        if (filePath !== outputDir && !filePath.startsWith(outputDir + path_1.default.sep)) {
            res.writeHead(403);
            res.end('Forbidden');
            return;
        }
        if (!fs_1.default.existsSync(filePath) || !fs_1.default.statSync(filePath).isFile()) {
            res.writeHead(404);
            res.end('Not found');
            return;
        }
        let body = fs_1.default.readFileSync(filePath);
        if (isHtml(filePath)) {
            body = Buffer.from(injectLiveReloadScript(body.toString('utf8')));
        }
        res.writeHead(200, { 'Content-Type': contentTypeFor(filePath) });
        res.end(body);
    };
}
function broadcast(wss, message) {
    for (const client of wss.clients) {
        if (client.readyState === ws_1.WebSocket.OPEN) {
            client.send(message);
        }
    }
}
/**
 * Start a live-reload development server.
 *
 * Performs an initial build, serves the generated site from outputDir over
 * HTTP, injects a WebSocket client script into HTML responses, watches the
 * content and templates directories for changes, rebuilds on change, and tells
 * connected browsers to reload when a rebuild completes.
 */
async function startDevServer(options = {}) {
    const contentDir = path_1.default.resolve(options.contentDir ?? 'content');
    const outputDir = path_1.default.resolve(options.outputDir ?? 'dist');
    const templatesDir = path_1.default.resolve(options.templatesDir ?? 'templates');
    const host = options.host ?? '127.0.0.1';
    const port = options.port ?? 3000;
    const debounce = options.debounce ?? 100;
    (0, index_1.buildSite)({ contentDir, outputDir, templatesDir });
    const server = http_1.default.createServer(createRequestHandler(outputDir));
    const wss = new ws_1.WebSocketServer({ server });
    const watcher = (0, chokidar_1.watch)([contentDir, templatesDir], { ignoreInitial: true });
    const watcherReady = new Promise((resolve) => {
        watcher.once('ready', () => resolve());
    });
    let timer = null;
    let building = false;
    let pending = false;
    const rebuild = () => {
        if (building) {
            pending = true;
            return;
        }
        building = true;
        pending = false;
        try {
            (0, index_1.buildSite)({ contentDir, outputDir, templatesDir });
            broadcast(wss, exports.RELOAD_MESSAGE);
        }
        catch (err) {
            console.error('Rebuild failed:', err);
        }
        finally {
            building = false;
            if (pending) {
                pending = false;
                scheduleRebuild();
            }
        }
    };
    const scheduleRebuild = () => {
        if (timer) {
            clearTimeout(timer);
        }
        timer = setTimeout(() => {
            timer = null;
            rebuild();
        }, debounce);
    };
    watcher.on('all', () => scheduleRebuild());
    await new Promise((resolve, reject) => {
        server.once('error', reject);
        server.listen(port, host, () => resolve());
    });
    await watcherReady;
    const address = server.address();
    const actualPort = typeof address === 'object' && address !== null ? address.port : port;
    return {
        server,
        port: actualPort,
        contentDir,
        outputDir,
        templatesDir,
        watcher,
        close() {
            return new Promise((resolve) => {
                if (timer) {
                    clearTimeout(timer);
                    timer = null;
                }
                for (const client of wss.clients) {
                    client.terminate();
                }
                watcher.close().then(() => {
                    wss.close(() => {
                        server.close(() => resolve());
                    });
                });
            });
        },
    };
}
//# sourceMappingURL=serve.js.map