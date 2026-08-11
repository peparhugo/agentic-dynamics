import http from 'http';
interface ServeOptions {
    port: number;
    content: string;
    output: string;
    templates: string;
}
interface ServerInstance {
    server: http.Server;
    close: () => Promise<void>;
    rebuild: () => void;
}
export declare function startServer(options: ServeOptions): ServerInstance;
export {};
//# sourceMappingURL=server.d.ts.map