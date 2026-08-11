import http from 'http';
export interface ServeOptions {
    content: string;
    output: string;
    templates: string;
    port: number;
}
export declare function createServer(options: ServeOptions): http.Server;
export declare function serve(options: ServeOptions): http.Server;
//# sourceMappingURL=server.d.ts.map