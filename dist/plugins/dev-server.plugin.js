"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.createDevServerPlugin = createDevServerPlugin;
const express_1 = __importDefault(require("express"));
const path_1 = __importDefault(require("path"));
const ws_1 = require("ws");
const http_1 = require("http");
const chokidar_1 = __importDefault(require("chokidar"));
const fs_1 = require("fs");
let devServerConfig = null;
let clients = [];
let server = null;
let watcher = null;
function broadcastReload() {
    const message = JSON.stringify({ type: 'reload' });
    clients = clients.filter(client => client.readyState === ws_1.WebSocket.OPEN);
    clients.forEach(client => {
        client.send(message);
    });
}
function injectReloadScript(html) {
    const script = `<script>
(function() {
  const ws = new WebSocket('ws://' + window.location.host);
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'reload') {
      window.location.reload();
    }
  };
  ws.onerror = () => {
    setTimeout(() => {
      window.location.reload();
    }, 1000);
  };
})();
</script>`;
    if (html.includes('</body>')) {
        return html.replace('</body>', script + '\n</body>');
    }
    return html + script;
}
async function serveFile(filePath) {
    try {
        let content = await fs_1.promises.readFile(filePath, 'utf-8');
        if (filePath.endsWith('.html')) {
            content = injectReloadScript(content);
        }
        return content;
    }
    catch (error) {
        throw error;
    }
}
function createDevServerPlugin(config) {
    return {
        name: 'dev-server',
        onStart: async (context) => {
            devServerConfig = config;
            const app = (0, express_1.default)();
            server = (0, http_1.createServer)(app);
            const wss = new ws_1.WebSocketServer({ server });
            wss.on('connection', (ws) => {
                clients.push(ws);
            });
            app.use(express_1.default.static(context.outputDir));
            app.get('*', async (req, res) => {
                let requestPath = req.path === '/' ? '/index.html' : req.path;
                if (!requestPath.endsWith('.html')) {
                    requestPath += '.html';
                }
                const filePath = path_1.default.join(context.outputDir, requestPath);
                try {
                    const content = await serveFile(filePath);
                    res.type('text/html').send(content);
                }
                catch (error) {
                    res.status(404).type('text/html').send(injectReloadScript(`<!DOCTYPE html>
<html>
<head><title>404 Not Found</title></head>
<body><h1>404 - Page not found</h1></body>
</html>`));
                }
            });
            server.listen(config.port, () => {
                console.log(`Dev server running at http://localhost:${config.port}`);
            });
            const watchDirs = [context.contentDir];
            if (context.templateDir) {
                watchDirs.push(context.templateDir);
            }
            watcher = chokidar_1.default.watch(watchDirs, {
                ignored: /node_modules/,
                persistent: true
            });
            let rebuildTimeout;
            watcher.on('change', () => {
                clearTimeout(rebuildTimeout);
                rebuildTimeout = setTimeout(async () => {
                    if (config.onRebuild) {
                        await config.onRebuild();
                    }
                    console.log('Build complete, reloading browser...');
                    broadcastReload();
                }, 300);
            });
        },
        onEnd: async (_context) => {
            if (watcher) {
                await watcher.close();
            }
            if (server) {
                server.close();
            }
        },
        onFile: async (page, _context) => {
            return page;
        }
    };
}
//# sourceMappingURL=dev-server.plugin.js.map