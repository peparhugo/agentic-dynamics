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
Object.defineProperty(exports, "__esModule", { value: true });
exports.DevServerPlugin = void 0;
exports.injectReloadScript = injectReloadScript;
const http = __importStar(require("http"));
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const ws_1 = require("ws");
const chokidar = __importStar(require("chokidar"));
const build_1 = require("../src/build");
function getReloadScript() {
    return `<script>
(function() {
  var ws = new WebSocket('ws://' + location.host);
  ws.onmessage = function(msg) {
    if (msg.data === 'reload') {
      location.reload();
    }
  };
})();
</script>`;
}
function injectReloadScript(html) {
    const script = getReloadScript();
    if (html.includes('</body>')) {
        return html.replace('</body>', script + '</body>');
    }
    if (html.includes('</html>')) {
        return html.replace('</html>', script + '</html>');
    }
    return html + script;
}
class DevServerPlugin {
    constructor() {
        this.name = 'dev-server';
        this.context = null;
        this.server = null;
        this.wss = null;
        this.watcher = null;
        this.connectedClients = new Set();
    }
    setContext(context) {
        this.context = context;
    }
    onStart() {
        const ctx = this.context;
        if (!ctx)
            return;
        const contentDir = ctx.contentDir;
        const outputDir = ctx.outputDir;
        const templatesDir = ctx.templatesDir || './templates';
        this.watcher = chokidar.watch([contentDir, templatesDir], {
            ignoreInitial: true,
        });
        this.wss = new ws_1.WebSocketServer({ noServer: true });
        const mimeTypes = {
            '.html': 'text/html',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.json': 'application/json',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.svg': 'image/svg+xml',
        };
        this.server = http.createServer((req, res) => {
            const url = req.url || '/';
            const filePath = url === '/' ? '/index.html' : url;
            const fullPath = path.join(path.resolve(outputDir), filePath);
            if (!fs.existsSync(fullPath)) {
                res.writeHead(404, { 'Content-Type': 'text/plain' });
                res.end('Not Found');
                return;
            }
            let content = fs.readFileSync(fullPath, 'utf-8');
            if (fullPath.endsWith('.html')) {
                content = injectReloadScript(content);
            }
            const ext = path.extname(fullPath).toLowerCase();
            const contentType = mimeTypes[ext] || 'application/octet-stream';
            res.writeHead(200, { 'Content-Type': contentType });
            res.end(content);
        });
        this.server.on('upgrade', (request, socket, head) => {
            if (this.wss) {
                this.wss.handleUpgrade(request, socket, head, (ws) => {
                    this.wss.emit('connection', ws, request);
                });
            }
        });
        if (this.wss) {
            this.wss.on('connection', (ws) => {
                this.connectedClients.add(ws);
                ws.on('close', () => {
                    this.connectedClients.delete(ws);
                });
            });
        }
        if (this.watcher) {
            const handleChange = (filePath) => {
                console.log(`File changed: ${filePath}`);
                try {
                    (0, build_1.build)(ctx.contentDir, ctx.outputDir, ctx.templatesDir);
                    console.log('Rebuild complete. Reloading clients...');
                    for (const client of this.connectedClients) {
                        if (client.readyState === ws_1.WebSocket.OPEN) {
                            client.send('reload');
                        }
                    }
                }
                catch (err) {
                    const message = err instanceof Error ? err.message : String(err);
                    console.error(`Rebuild error: ${message}`);
                }
            };
            this.watcher.on('change', handleChange);
        }
    }
    afterBuild(_pages) {
        for (const client of this.connectedClients) {
            if (client.readyState === ws_1.WebSocket.OPEN) {
                client.send('reload');
            }
        }
    }
    onEnd() {
        if (this.watcher) {
            this.watcher.close();
        }
        if (this.server) {
            this.server.close();
        }
    }
    listen(port, callback) {
        if (this.server) {
            this.server.listen(port, () => {
                console.log(`Dev server running at http://localhost:${port}/`);
                if (callback)
                    callback();
            });
        }
        return this.server;
    }
    getServer() {
        return this.server;
    }
}
exports.DevServerPlugin = DevServerPlugin;
//# sourceMappingURL=dev-server-plugin.js.map