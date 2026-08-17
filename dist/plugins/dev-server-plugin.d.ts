import { Plugin } from '../plugin';
import { BuildOptions, DevServer, ServeOptions, Site } from '../types';
export declare const RELOAD_MESSAGE = "reload";
export declare const LIVE_RELOAD_SCRIPT = "<script>\n(function () {\n  var socket = new WebSocket('ws://' + window.location.host);\n  socket.addEventListener('message', function (event) {\n    if (event.data === 'reload') {\n      window.location.reload();\n    }\n  });\n})();\n</script>";
export declare function injectLiveReloadScript(html: string, script?: string): string;
/**
 * Built-in plugin that owns the live-reload development server: it performs an
 * initial build, serves the generated site over HTTP, injects the WebSocket
 * client script into HTML responses, watches the content and templates
 * directories for changes, rebuilds on change, and tells connected browsers to
 * reload when a rebuild completes.
 */
export declare class DevServerPlugin implements Plugin {
    private readonly build;
    name: string;
    private server?;
    private wss?;
    private watcher?;
    private timer;
    private building;
    private pending;
    private readonly contentDir;
    private readonly outputDir;
    private readonly templatesDir;
    private readonly host;
    private readonly port;
    private readonly debounce;
    constructor(build: (options: BuildOptions) => Site, options?: ServeOptions);
    onStart(): void;
    onEnd(): Promise<void>;
    start(): Promise<DevServer>;
    close(): Promise<void>;
    private rebuild;
    private scheduleRebuild;
    private broadcast;
}
