import http from 'http';
export interface DevServerOptions {
    contentDir: string;
    outputDir: string;
    templatesDir: string;
    port: number;
}
export declare function startDevServer(options: DevServerOptions): http.Server;
