import http from 'http';
export declare const LIVE_RELOAD_SCRIPT = "<script>\n(function () {\n  var ws = new WebSocket('ws://' + location.host);\n  ws.onmessage = function (msg) {\n    if (msg.data === 'reload') location.reload();\n  };\n})();\n</script>";
export interface ServerOptions {
    content: string;
    output: string;
    templates?: string;
    port: number;
}
export declare function injectLiveReload(html: string): string;
export declare function createServer(options: ServerOptions): http.Server;
export declare function startServer(options: ServerOptions): http.Server;
//# sourceMappingURL=server.d.ts.map