export interface ServeOptions {
    content: string;
    output: string;
    templates?: string;
    port?: number;
}
export interface DevServer {
    port: number;
    reload(): void;
    close(): Promise<void>;
}
export declare function liveReloadScript(): string;
export declare function injectLiveReload(html: string): string;
export declare function serve(options: ServeOptions): Promise<DevServer>;
