import type { Plugin } from './plugin';
import { liveReloadScript, injectLiveReload } from './liveReload';
export { liveReloadScript, injectLiveReload };
export interface ServeOptions {
    content: string;
    output: string;
    templates?: string;
    port?: number;
    config?: string | false;
    plugins?: Plugin[];
}
export interface DevServer {
    port: number;
    reload(): void;
    close(): Promise<void>;
}
export declare function serve(options: ServeOptions): Promise<DevServer>;
