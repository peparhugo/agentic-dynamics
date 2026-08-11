export interface ServeOptions {
    content: string;
    output: string;
    templates: string;
    port: number;
}
export interface DevServer {
    close: () => Promise<void>;
    port: number;
}
export declare function startDevServer(options: ServeOptions): Promise<DevServer>;
//# sourceMappingURL=server.d.ts.map