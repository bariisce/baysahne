/**
 * Address to load an image from.
 *
 * With local storage the API serves files under `/media/` and this app proxies that path (see the rewrites
 * in next.config.ts). The API writes its own idea of a public address into the URL — a LAN address meant
 * for phones, another port, an old IP — which the browser may not reach and the Content-Security-Policy
 * does not allow. Such images are therefore always loaded through the panel's own origin.
 * Anything else (an S3 bucket or CDN) is used as it is.
 */
export function mediaSrc(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  try {
    const { pathname, search } = new URL(url, "http://panel.invalid");
    return pathname.startsWith("/media/") ? pathname + search : url;
  } catch {
    return url;
  }
}
