import * as http from 'http';
export { injectReloadScript } from '../plugins/dev-server-plugin';
export interface ServeOptions {
    content?: string;
    output?: string;
    templates?: string;
    port?: number;
}
export declare function serve(options: ServeOptions): http.Server;
//# sourceMappingURL=serve.d.ts.map