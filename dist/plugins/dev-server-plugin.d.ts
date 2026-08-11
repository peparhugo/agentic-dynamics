import * as http from 'http';
import { Page } from '../src/types';
import { Plugin, BuildContext } from '../src/plugin';
export declare function injectReloadScript(html: string): string;
export declare class DevServerPlugin implements Plugin {
    name: string;
    private context;
    private server;
    private wss;
    private watcher;
    private connectedClients;
    setContext(context: BuildContext): void;
    onStart(): void;
    afterBuild(_pages: Page[]): void;
    onEnd(): void;
    listen(port: number, callback?: () => void): http.Server;
    getServer(): http.Server | null;
}
//# sourceMappingURL=dev-server-plugin.d.ts.map