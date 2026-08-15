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
exports.reloadClientScript = reloadClientScript;
exports.injectReloadScript = injectReloadScript;
exports.startDevServer = startDevServer;
const http_1 = require("http");
const fs_1 = require("fs");
const path = __importStar(require("path"));
const chokidar_1 = __importDefault(require("chokidar"));
const ws_1 = require("ws");
const generator_1 = require("./generator");
const DEFAULT_PORT = 3000;
const LIVERELOAD_PATH = '/__ssg_livereload';
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
/**
 * Browser-side client that connects to the live-reload WebSocket endpoint and
 * reloads the page when a `reload` message arrives.
 */
function reloadClientScript() {
    return `<script>
(function () {
  var reconnectDelay = 500;
  function connect() {
    var ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '${LIVERELOAD_PATH}');
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
        res.end(injectReloadScript(body));
        return;
    }
    res.writeHead(200, { 'Content-Type': MIME_TYPES[ext] ?? 'application/octet-stream' });
    res.end(data);
}
/**
 * Start a live-reload development server.
 *
 * Performs an initial build, serves the built site from `outputDir`, watches
 * `contentDir` and `templatesDir` for changes, rebuilds on change, and tells
 * connected browsers to reload once a rebuild finishes.
 */
async function startDevServer(options) {
    const port = options.port ?? DEFAULT_PORT;
    const contentDir = options.contentDir;
    const outputDir = options.outputDir;
    const templatesDir = options.templatesDir ?? 'templates';
    await (0, generator_1.build)({ contentDir, outputDir, templatesDir });
    const wss = new ws_1.WebSocketServer({ noServer: true });
    const server = (0, http_1.createServer)((req, res) => {
        serveFile(req.url ?? '/', outputDir, res).catch(() => {
            res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' });
            res.end('Internal Server Error');
        });
    });
    server.on('upgrade', (req, socket, head) => {
        const pathname = (req.url ?? '').split('?')[0];
        if (pathname === LIVERELOAD_PATH) {
            wss.handleUpgrade(req, socket, head, (ws) => {
                wss.emit('connection', ws, req);
            });
        }
        else {
            socket.destroy();
        }
    });
    const broadcast = (message) => {
        for (const client of wss.clients) {
            if (client.readyState === ws_1.WebSocket.OPEN) {
                client.send(message);
            }
        }
    };
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
    watcher.on('error', () => {
        // Watcher errors are non-fatal for the dev server.
    });
    const watcherReady = new Promise((resolve) => {
        watcher.once('ready', resolve);
    });
    let timer = null;
    let queue = Promise.resolve();
    const rebuild = async () => {
        try {
            await (0, generator_1.build)({ contentDir, outputDir, templatesDir });
            broadcast('reload');
        }
        catch (err) {
            const message = err instanceof Error ? err.message : String(err);
            broadcast(JSON.stringify({ type: 'error', message }));
        }
    };
    watcher.on('all', () => {
        if (timer) {
            clearTimeout(timer);
        }
        timer = setTimeout(() => {
            timer = null;
            queue = queue.then(rebuild);
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
    const actualPort = address && typeof address === 'object' ? address.port : port;
    return {
        server,
        wss,
        port: actualPort,
        close: async () => {
            if (timer) {
                clearTimeout(timer);
            }
            for (const client of wss.clients) {
                client.terminate();
            }
            await watcher.close();
            await new Promise((resolve) => wss.close(() => resolve()));
            server.closeAllConnections();
            await new Promise((resolve) => server.close(() => resolve()));
        },
    };
}
