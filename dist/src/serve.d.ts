import http from 'http';
export interface ServeOptions {
    contentDir: string;
    outputDir: string;
    templatesDir?: string;
    port: number;
}
export interface ServerInstance {
    server: http.Server;
    ready: Promise<void>;
    close(): Promise<void>;
}
export declare function serve(options: ServeOptions): ServerInstance;
