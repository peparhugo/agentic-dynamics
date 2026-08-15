export interface DevServerOptions {
    contentDir: string;
    outputDir: string;
    templatesDir?: string;
    port?: number;
}
export declare class DevServer {
    private contentDir;
    private outputDir;
    private templatesDir;
    private port;
    private generator;
    private devServerPlugin;
    constructor(options: DevServerOptions);
    start(): Promise<void>;
    stop(): Promise<void>;
    private injectLiveReloadScript;
}
//# sourceMappingURL=dev-server.d.ts.map