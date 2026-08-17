import http from 'http';
import { FSWatcher } from 'chokidar';
export declare const RELOAD_MESSAGE = "reload";
export declare const LIVE_RELOAD_SCRIPT = "<script>\n(function () {\n  var socket = new WebSocket('ws://' + window.location.host);\n  socket.addEventListener('message', function (event) {\n    if (event.data === 'reload') {\n      window.location.reload();\n    }\n  });\n})();\n</script>";
export interface ServeOptions {
    contentDir?: string;
    outputDir?: string;
    templatesDir?: string;
    port?: number;
    host?: string;
    debounce?: number;
}
export interface DevServer {
    server: http.Server;
    port: number;
    contentDir: string;
    outputDir: string;
    templatesDir: string;
    watcher: FSWatcher;
    close(): Promise<void>;
}
export declare function injectLiveReloadScript(html: string, script?: string): string;
/**
 * Start a live-reload development server.
 *
 * Performs an initial build, serves the generated site from outputDir over
 * HTTP, injects a WebSocket client script into HTML responses, watches the
 * content and templates directories for changes, rebuilds on change, and tells
 * connected browsers to reload when a rebuild completes.
 */
export declare function startDevServer(options?: ServeOptions): Promise<DevServer>;
