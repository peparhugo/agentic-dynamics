import { Plugin } from '../plugin';
interface DevServerConfig {
    port: number;
    onRebuild?: () => Promise<void>;
}
export declare function createDevServerPlugin(config: DevServerConfig): Plugin;
export {};
//# sourceMappingURL=dev-server.plugin.d.ts.map