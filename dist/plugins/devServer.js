"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.DevServerPlugin = exports.REBUILD_DELAY_MS = exports.RELOAD_MESSAGE = exports.LIVERELOAD_PATH = exports.DEFAULT_PORT = void 0;
exports.clientScript = clientScript;
exports.hasLiveReload = hasLiveReload;
exports.injectLiveReload = injectLiveReload;
exports.createRequestHandler = createRequestHandler;
exports.broadcastReload = broadcastReload;
const fs_1 = __importDefault(require("fs"));
const http_1 = __importDefault(require("http"));
const path_1 = __importDefault(require("path"));
const chokidar_1 = require("chokidar");
const ws_1 = require("ws");
exports.DEFAULT_PORT = 3000;
exports.LIVERELOAD_PATH = '/__livereload';
exports.RELOAD_MESSAGE = 'reload';
exports.REBUILD_DELAY_MS = 100;
const MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.htm': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.mjs': 'text/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.txt': 'text/plain; charset=utf-8',
    '.xml': 'application/xml; charset=utf-8',
    '.webmanifest': 'application/manifest+json; charset=utf-8',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.ttf': 'font/ttf',
    '.map': 'application/json; charset=utf-8',
};
function clientScript() {
    return [
        '<script id="__livereload">',
        '(function () {',
        "  var proto = location.protocol === 'https:' ? 'wss://' : 'ws://';",
        `  var ws = new WebSocket(proto + location.host + '${exports.LIVERELOAD_PATH}');`,
        `  ws.onmessage = function (event) {`,
        `    if (event.data === '${exports.RELOAD_MESSAGE}') { location.reload(); }`,
        '  };',
        '})();',
        '</script>',
    ].join('\n');
}
function hasLiveReload(html) {
    return html.includes('id="__livereload"');
}
function injectLiveReload(html) {
    if (hasLiveReload(html))
        return html;
    const script = clientScript();
    const bodyEnd = html.lastIndexOf('</body>');
    if (bodyEnd !== -1) {
        return html.slice(0, bodyEnd) + script + html.slice(bodyEnd);
    }
    const htmlEnd = html.lastIndexOf('</html>');
    if (htmlEnd !== -1) {
        return html.slice(0, htmlEnd) + script + html.slice(htmlEnd);
    }
    return html + script;
}
function contentType(filePath) {
    return MIME_TYPES[path_1.default.extname(filePath).toLowerCase()] || 'application/octet-stream';
}
function isHtmlFile(filePath) {
    return /\.html?$/i.test(filePath);
}
function createRequestHandler(outputDir) {
    return (req, res) => {
        let pathname;
        try {
            pathname = decodeURIComponent(new URL(req.url || '/', 'http://localhost').pathname);
        }
        catch {
            res.writeHead(400, { 'Content-Type': 'text/plain; charset=utf-8' });
            res.end('Bad request');
            return;
        }
        if (pathname === '/')
            pathname = '/index.html';
        const resolvedRoot = path_1.default.resolve(outputDir);
        const filePath = path_1.default.join(resolvedRoot, pathname);
        if (!filePath.startsWith(resolvedRoot + path_1.default.sep)) {
            res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
            res.end('Forbidden');
            return;
        }
        fs_1.default.readFile(filePath, (err, data) => {
            if (err) {
                res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
                res.end('Not found');
                return;
            }
            let body = data;
            if (isHtmlFile(filePath) && !hasLiveReload(data.toString('utf8'))) {
                body = injectLiveReload(data.toString('utf8'));
            }
            res.writeHead(200, { 'Content-Type': contentType(filePath) });
            res.end(body);
        });
    };
}
function broadcastReload(wss) {
    for (const client of wss.clients) {
        if (client.readyState === ws_1.WebSocket.OPEN) {
            client.send(exports.RELOAD_MESSAGE);
        }
    }
}
class DevServerPlugin {
    constructor() {
        this.name = 'dev-server';
        this.timer = null;
        this.port = exports.DEFAULT_PORT;
    }
    setPort(port) {
        this.port = port;
    }
    onStart(ctx) {
        const server = http_1.default.createServer(createRequestHandler(ctx.outputDir));
        const wss = new ws_1.WebSocketServer({ server, path: exports.LIVERELOAD_PATH });
        const watchPaths = [ctx.contentDir];
        if (fs_1.default.existsSync(ctx.templatesDir))
            watchPaths.push(ctx.templatesDir);
        const watcher = (0, chokidar_1.watch)(watchPaths, { ignoreInitial: true });
        watcher.on('all', () => {
            if (this.timer)
                clearTimeout(this.timer);
            this.timer = setTimeout(() => {
                this.timer = null;
                if (typeof ctx.rebuild === 'function') {
                    ctx.rebuild();
                }
                broadcastReload(wss);
            }, exports.REBUILD_DELAY_MS);
        });
        server.on('listening', () => {
            const addr = server.address();
            if (addr) {
                this.port = addr.port;
                if (this.handle) {
                    this.handle.port = addr.port;
                }
                console.log(`[ssg serve] http://localhost:${addr.port}`);
            }
        });
        server.listen(this.port);
        this.server = server;
        this.wss = wss;
        this.watcher = watcher;
        this.handle = {
            server,
            wss,
            watcher,
            port: this.port,
            close: () => new Promise((resolve) => {
                if (this.timer) {
                    clearTimeout(this.timer);
                    this.timer = null;
                }
                watcher.close().then(() => {
                    wss.close(() => {
                        server.close(() => resolve());
                    });
                });
            }),
        };
    }
    getHandle() {
        if (!this.handle) {
            throw new Error('dev server not started');
        }
        return this.handle;
    }
}
exports.DevServerPlugin = DevServerPlugin;
