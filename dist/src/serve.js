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
exports.injectReloadScript = injectReloadScript;
exports.serve = serve;
const http = __importStar(require("http"));
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const ws_1 = require("ws");
const chokidar = __importStar(require("chokidar"));
const build_1 = require("./build");
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
function serve(options) {
    const contentDir = options.content || './content';
    const outputDir = options.output || './dist';
    const templatesDir = options.templates || './templates';
    const port = options.port || 3000;
    (0, build_1.build)(contentDir, outputDir, templatesDir);
    const watcher = chokidar.watch([contentDir, templatesDir], {
        ignoreInitial: true,
    });
    const wss = new ws_1.WebSocketServer({ noServer: true });
    const mimeTypes = {
        '.html': 'text/html',
        '.css': 'text/css',
        '.js': 'application/javascript',
        '.json': 'application/json',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.svg': 'image/svg+xml',
    };
    const server = http.createServer((req, res) => {
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
    server.on('upgrade', (request, socket, head) => {
        wss.handleUpgrade(request, socket, head, (ws) => {
            wss.emit('connection', ws, request);
        });
    });
    const connectedClients = new Set();
    wss.on('connection', (ws) => {
        connectedClients.add(ws);
        ws.on('close', () => {
            connectedClients.delete(ws);
        });
    });
    watcher.on('change', (filePath) => {
        console.log(`File changed: ${filePath}`);
        try {
            (0, build_1.build)(contentDir, outputDir, templatesDir);
            console.log('Rebuild complete. Reloading clients...');
            for (const client of connectedClients) {
                if (client.readyState === ws_1.WebSocket.OPEN) {
                    client.send('reload');
                }
            }
        }
        catch (err) {
            const message = err instanceof Error ? err.message : String(err);
            console.error(`Rebuild error: ${message}`);
        }
    });
    server.listen(port, () => {
        console.log(`Dev server running at http://localhost:${port}/`);
    });
    return server;
}
//# sourceMappingURL=serve.js.map