"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.DevServerPlugin = void 0;
const http_1 = require("http");
const fs_1 = require("fs");
const path = __importStar(require("path"));
const chokidar_1 = __importDefault(require("chokidar"));
const ws_1 = require("ws");
const livereload_1 = require("../src/livereload");
const DEFAULT_PORT = 3000;
const REBUILD_DEBOUNCE_MS = 100;
const WATCHER_SETTLE_MS = 250;
const MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.htm': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.mjs': 'text/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.xml': 'application/xml; charset=utf-8',
    '.txt': 'text/plain; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.ico': 'image/x-icon',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.ttf': 'font/ttf',
    '.pdf': 'application/pdf',
    '.map': 'application/json',
};
function resolveFilePath(urlPath, outputDir) {
    let pathname;
    try {
        pathname = decodeURIComponent(urlPath.split('?')[0]).split('#')[0];
    }
    catch {
        return null;
    }
    const root = path.resolve(outputDir);
    const clean = pathname.replace(/^\/+/, '');
    const candidate = path.resolve(root, clean);
    if (candidate !== root && !candidate.startsWith(root + path.sep)) {
        return null;
    }
    return candidate;
}
async function fileStat(target) {
    try {
        const stat = await fs_1.promises.stat(target);
        return { isDirectory: stat.isDirectory() };
    }
    catch {
        return null;
    }
}
async function serveFile(reqUrl, outputDir, res) {
    const file = resolveFilePath(reqUrl, outputDir);
    if (!file) {
        res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
        res.end('Forbidden');
        return;
    }
    let target = file;
    let stat = await fileStat(target);
    if (stat && stat.isDirectory) {
        target = path.join(target, 'index.html');
        stat = await fileStat(target);
    }
    if (!stat) {
        res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
        res.end('Not Found');
        return;
    }
    const ext = path.extname(target).toLowerCase();
    const data = await fs_1.promises.readFile(target);
    if (ext === '.html') {
        const body = data.toString('utf8');
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end((0, livereload_1.injectReloadScript)(body));
        return;
    }
    res.writeHead(200, { 'Content-Type': MIME_TYPES[ext] ?? 'application/octet-stream' });
    res.end(data);
}
/**
 * Built-in plugin implementing the live-reload development server.
 *
 * During `onStart` it performs an initial build, starts an HTTP server that
 * serves the built site, and watches the content and template directories. On
 * change it rebuilds through the core engine and tells connected browsers to
 * reload.
 */
class DevServerPlugin {
    constructor() {
        this.name = 'dev-server';
        this.port = DEFAULT_PORT;
        this.timer = null;
        this.queue = Promise.resolve();
    }
    async onStart(ctx) {
        this.ctx = ctx;
        await this.setup();
    }
    getServer() {
        return {
            server: this.server,
            wss: this.wss,
            port: this.port,
            close: () => this.close(),
        };
    }
    async setup() {
        const options = this.ctx.options;
        const contentDir = options.contentDir;
        const outputDir = options.outputDir;
        const templatesDir = options.templatesDir ?? 'templates';
        const port = options.port ?? DEFAULT_PORT;
        await this.ctx.engine.rebuild();
        const wss = new ws_1.WebSocketServer({ noServer: true });
        this.wss = wss;
        const server = (0, http_1.createServer)((req, res) => {
            serveFile(req.url ?? '/', outputDir, res).catch(() => {
                res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' });
                res.end('Internal Server Error');
            });
        });
        this.server = server;
        server.on('upgrade', (req, socket, head) => {
            const pathname = (req.url ?? '').split('?')[0];
            if (pathname === livereload_1.LIVERELOAD_PATH) {
                wss.handleUpgrade(req, socket, head, (ws) => {
                    wss.emit('connection', ws, req);
                });
            }
            else {
                socket.destroy();
            }
        });
        const watcher = chokidar_1.default.watch([contentDir, templatesDir], {
            ignoreInitial: true,
            ignored: (watchedPath) => {
                const normalized = path.resolve(watchedPath);
                const out = path.resolve(outputDir);
                if (normalized === out || normalized.startsWith(out + path.sep)) {
                    return true;
                }
                const segments = normalized.split(path.sep);
                if (segments.includes('node_modules')) {
                    return true;
                }
                if (path.basename(normalized).startsWith('.')) {
                    return true;
                }
                return false;
            },
        });
        this.watcher = watcher;
        watcher.on('error', () => {
            // Watcher errors are non-fatal for the dev server.
        });
        const watcherReady = new Promise((resolve) => {
            watcher.once('ready', resolve);
        });
        watcher.on('all', () => {
            if (this.timer) {
                clearTimeout(this.timer);
            }
            this.timer = setTimeout(() => {
                this.timer = null;
                this.queue = this.queue.then(() => this.rebuild());
            }, REBUILD_DEBOUNCE_MS);
        });
        await watcherReady;
        await new Promise((resolve) => setTimeout(resolve, WATCHER_SETTLE_MS));
        await new Promise((resolve, reject) => {
            server.once('error', reject);
            server.listen(port, () => {
                server.removeListener('error', reject);
                resolve();
            });
        });
        const address = server.address();
        this.port = address && typeof address === 'object' ? address.port : port;
    }
    broadcast(message) {
        for (const client of this.wss.clients) {
            if (client.readyState === ws_1.WebSocket.OPEN) {
                client.send(message);
            }
        }
    }
    async rebuild() {
        try {
            await this.ctx.engine.rebuild();
            this.broadcast('reload');
        }
        catch (err) {
            const message = err instanceof Error ? err.message : String(err);
            this.broadcast(JSON.stringify({ type: 'error', message }));
        }
    }
    async close() {
        if (this.timer) {
            clearTimeout(this.timer);
        }
        for (const client of this.wss.clients) {
            client.terminate();
        }
        await this.watcher.close();
        await new Promise((resolve) => this.wss.close(() => resolve()));
        this.server.closeAllConnections();
        await new Promise((resolve) => this.server.close(() => resolve()));
    }
}
exports.DevServerPlugin = DevServerPlugin;
