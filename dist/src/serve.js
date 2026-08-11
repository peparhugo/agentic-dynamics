"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.serve = serve;
const http_1 = __importDefault(require("http"));
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const ws_1 = require("ws");
const chokidar_1 = __importDefault(require("chokidar"));
const build_1 = require("./build");
const LIVE_RELOAD_SCRIPT = '<script>(function(){var s=new WebSocket(\'ws://\'+location.host+\'/__ssg_livereload\');s.onmessage=function(e){if(e.data===\'reload\')location.reload();};})();</script>';
const MIME_TYPES = {
    '.html': 'text/html',
    '.css': 'text/css',
    '.js': 'application/javascript',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
};
function getMimeType(filePath) {
    const ext = path_1.default.extname(filePath).toLowerCase();
    return MIME_TYPES[ext] || 'application/octet-stream';
}
function serve(options) {
    const contentDir = path_1.default.resolve(options.contentDir);
    const outputDir = path_1.default.resolve(options.outputDir);
    const { templatesDir, port } = options;
    const buildOpts = { contentDir, outputDir, templatesDir };
    (0, build_1.build)(buildOpts);
    const wss = new ws_1.WebSocketServer({ noServer: true });
    const server = http_1.default.createServer((req, res) => {
        try {
            if (!req.url) {
                res.writeHead(404);
                res.end();
                return;
            }
            const urlPath = req.url.split('?')[0];
            let filePath;
            if (urlPath === '/') {
                filePath = path_1.default.join(outputDir, 'index.html');
            }
            else {
                filePath = path_1.default.join(outputDir, urlPath);
                if (fs_1.default.existsSync(filePath) && fs_1.default.statSync(filePath).isDirectory()) {
                    filePath = path_1.default.join(filePath, 'index.html');
                }
            }
            filePath = path_1.default.resolve(filePath);
            if (!filePath.startsWith(outputDir + path_1.default.sep) && filePath !== path_1.default.join(outputDir, 'index.html')) {
                res.writeHead(403);
                res.end();
                return;
            }
            if (!fs_1.default.existsSync(filePath) || !fs_1.default.statSync(filePath).isFile()) {
                res.writeHead(404);
                res.end('Not Found');
                return;
            }
            const ext = path_1.default.extname(filePath).toLowerCase();
            const mimeType = getMimeType(filePath);
            let content = fs_1.default.readFileSync(filePath);
            if (ext === '.html') {
                const html = content.toString('utf-8');
                const injectedHtml = html.replace('</body>', LIVE_RELOAD_SCRIPT + '</body>');
                content = Buffer.from(injectedHtml, 'utf-8');
            }
            res.writeHead(200, { 'Content-Type': mimeType });
            res.end(content);
        }
        catch {
            res.writeHead(500);
            res.end('Internal Server Error');
        }
    });
    server.on('upgrade', (request, socket, head) => {
        if (request.url === '/__ssg_livereload') {
            wss.handleUpgrade(request, socket, head, (ws) => {
                wss.emit('connection', ws, request);
            });
        }
        else {
            socket.destroy();
        }
    });
    let rebuildTimeout = null;
    const clients = new Set();
    wss.on('connection', (ws) => {
        clients.add(ws);
        ws.on('close', () => {
            clients.delete(ws);
        });
    });
    function triggerRebuild() {
        if (rebuildTimeout) {
            clearTimeout(rebuildTimeout);
        }
        rebuildTimeout = setTimeout(() => {
            try {
                (0, build_1.build)(buildOpts);
                for (const client of clients) {
                    if (client.readyState === ws_1.WebSocket.OPEN) {
                        client.send('reload');
                    }
                }
            }
            catch {
                // Silently handle build errors during watch
            }
        }, 300);
    }
    const watchDirs = [contentDir];
    if (templatesDir) {
        watchDirs.push(path_1.default.resolve(templatesDir));
    }
    const watcher = chokidar_1.default.watch(watchDirs, {
        ignoreInitial: true,
        usePolling: true,
        interval: 200,
    });
    watcher.on('all', () => {
        triggerRebuild();
    });
    const ready = new Promise((resolve) => {
        let watcherReady = false;
        let serverReady = false;
        const check = () => {
            if (watcherReady && serverReady)
                resolve();
        };
        watcher.on('ready', () => {
            watcherReady = true;
            check();
        });
        server.once('listening', () => {
            serverReady = true;
            check();
        });
    });
    server.listen(port);
    return {
        server,
        ready,
        close() {
            return new Promise((resolve) => {
                watcher.close();
                wss.close(() => {
                    for (const client of clients) {
                        client.terminate();
                    }
                    clients.clear();
                    server.close(() => resolve());
                });
            });
        },
    };
}
