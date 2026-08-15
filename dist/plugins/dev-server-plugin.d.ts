import { Plugin } from '../plugin';
import { ServeOptions } from '../serve';
/**
 * Built-in plugin that starts the development server.
 *
 * `onStart` builds the site, serves it over HTTP and begins watching the
 * content/templates directories for changes. `onEnd` tears the server down.
 */
export declare class DevServerPlugin implements Plugin {
    private options;
    name: string;
    private handle?;
    constructor(options?: ServeOptions);
    onStart(): Promise<void>;
    onEnd(): Promise<void>;
    get address(): string | undefined;
    get port(): number | undefined;
}
