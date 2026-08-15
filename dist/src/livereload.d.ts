export declare const LIVERELOAD_PATH = "/__ssg_livereload";
/**
 * Browser-side client that connects to the live-reload WebSocket endpoint and
 * reloads the page when a `reload` message arrives.
 */
export declare function reloadClientScript(): string;
/**
 * Inject the live-reload client script into an HTML document just before the
 * closing `</body>` tag.
 */
export declare function injectReloadScript(html: string): string;
