declare module "event-source-polyfill" {
  interface EventSourcePolyfillInit extends EventSourceInit {
    headers?: Record<string, string>;
    payload?: string;
    method?: string;
  }

  export class EventSourcePolyfill extends EventSource {
    constructor(url: string, eventSourceInitDict?: EventSourcePolyfillInit);
  }
}
