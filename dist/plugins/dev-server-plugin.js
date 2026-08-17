"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.DevServerPlugin = exports.LIVE_RELOAD_SCRIPT = exports.RELOAD_MESSAGE = void 0;
exports.injectLiveReloadScript = injectLiveReloadScript;
const fs_1 = __importDefault(require("fs"));
const http_1 = __importDefault(require("http"));
const path_1 = __importDefault(require("path"));
const chokidar_1 = require("chokidar");
const ws_1 = require("ws");
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
/**
 * Built-in plugin that owns the live-reload development server: it performs an
 * initial build, serves the generated site over HTTP, injects the WebSocket
 * client script into HTML responses, watches the content and templates
 * directories for changes, rebuilds on change, and tells connected browsers to
 * reload when a rebuild completes.
 */
class DevServerPlugin {
    constructor(build, options = {}) {
        this.build = build;
        this.name = 'dev-server';
        this.timer = null;
        this.building = false;
        this.pending = false;
        this.contentDir = path_1.default.resolve(options.contentDir ?? 'content');
        this.outputDir = path_1.default.resolve(options.outputDir ?? 'dist');
        this.templatesDir = path_1.default.resolve(options.templatesDir ?? 'templates');
        this.host = options.host ?? '127.0.0.1';
        this.port = options.port ?? 3000;
        this.debounce = options.debounce ?? 100;
    }
    onStart() {
        // The initial build and server setup are performed by start().
    }
    async onEnd() {
        await this.close();
    }
    async start() {
        await this.onStart();
        this.build({
            contentDir: this.contentDir,
            outputDir: this.outputDir,
            templatesDir: this.templatesDir,
        });
        const server = http_1.default.createServer(createRequestHandler(this.outputDir));
        const wss = new ws_1.WebSocketServer({ server });
        const watcher = (0, chokidar_1.watch)([this.contentDir, this.templatesDir], { ignoreInitial: true });
        const watcherReady = new Promise((resolve) => {
            watcher.once('ready', () => resolve());
        });
        watcher.on('all', () => this.scheduleRebuild());
        await new Promise((resolve, reject) => {
            server.once('error', reject);
            server.listen(this.port, this.host, () => resolve());
        });
        await watcherReady;
        this.server = server;
        this.wss = wss;
        this.watcher = watcher;
        const address = server.address();
        const actualPort = typeof address === 'object' && address !== null ? address.port : this.port;
        return {
            server,
            port: actualPort,
            contentDir: this.contentDir,
            outputDir: this.outputDir,
            templatesDir: this.templatesDir,
            watcher,
            close: () => this.close(),
        };
    }
    async close() {
        const { server, wss, watcher } = this;
        return new Promise((resolve) => {
            if (this.timer) {
                clearTimeout(this.timer);
                this.timer = null;
            }
            if (wss) {
                for (const client of wss.clients) {
                    client.terminate();
                }
            }
            const finish = () => {
                if (wss) {
                    wss.close(() => {
                        if (server) {
                            server.close(() => resolve());
                        }
                        else {
                            resolve();
                        }
                    });
                }
                else if (server) {
                    server.close(() => resolve());
                }
                else {
                    resolve();
                }
            };
            if (watcher) {
                watcher.close().then(finish);
            }
            else {
                finish();
            }
        });
    }
    rebuild() {
        if (this.building) {
            this.pending = true;
            return;
        }
        this.building = true;
        this.pending = false;
        try {
            this.build({
                contentDir: this.contentDir,
                outputDir: this.outputDir,
                templatesDir: this.templatesDir,
            });
            this.broadcast(exports.RELOAD_MESSAGE);
        }
        catch (err) {
            console.error('Rebuild failed:', err);
        }
        finally {
            this.building = false;
            if (this.pending) {
                this.pending = false;
                this.scheduleRebuild();
            }
        }
    }
    scheduleRebuild() {
        if (this.timer) {
            clearTimeout(this.timer);
        }
        this.timer = setTimeout(() => {
            this.timer = null;
            this.rebuild();
        }, this.debounce);
    }
    broadcast(message) {
        if (!this.wss) {
            return;
        }
        for (const client of this.wss.clients) {
            if (client.readyState === ws_1.WebSocket.OPEN) {
                client.send(message);
            }
        }
    }
}
exports.DevServerPlugin = DevServerPlugin;
//# sourceMappingURL=dev-server-plugin.js.map