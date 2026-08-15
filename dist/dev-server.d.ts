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
    private httpServer;
    private wsServer;
    private generator;
    private isBuilding;
    constructor(options: DevServerOptions);
    private rebuild;
    private notifyClients;
    private injectLiveReloadScript;
    private createHttpServer;
    start(): Promise<void>;
    stop(): Promise<void>;
}
//# sourceMappingURL=dev-server.d.ts.map