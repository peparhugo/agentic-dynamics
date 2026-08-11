import * as http from 'http';
export declare function injectReloadScript(html: string): string;
export interface ServeOptions {
    content?: string;
    output?: string;
    templates?: string;
    port?: number;
}
export declare function serve(options: ServeOptions): http.Server;
//# sourceMappingURL=serve.d.ts.map