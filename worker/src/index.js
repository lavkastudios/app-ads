// Cloudflare Worker "app-ads" for lavkastudios.com/app-ads.txt
// Serves dist/app-ads.txt from this repository (updated by the GitHub Action after all checks).
// Answers on any path of its routes, like the previous Worker.
// Fallbacks: last good copy from the cache, then the old copy in KV (binding app_ads, key "app-ads.txt").
// Publishing a new version = a commit to this repository.
const SOURCE = "https://raw.githubusercontent.com/lavkastudios/app-ads/main/dist/app-ads.txt";
const LAST_GOOD = "https://lavkastudios.com/__app-ads-last-good";

function looksValid(t) {
  return t.startsWith("ownerdomain=lavkastudios.com") && !t.includes("<") && t.length > 20000;
}

export default {
  async fetch(request, env, ctx) {
    const cache = caches.default;
    let body = null;
    let src = "github";
    try {
      const r = await fetch(SOURCE, { cf: { cacheTtl: 300, cacheEverything: true } });
      if (r.ok) {
        const t = await r.text();
        if (looksValid(t)) body = t;
      }
    } catch (e) {}
    if (body) {
      ctx.waitUntil(cache.put(LAST_GOOD, new Response(body, { headers: { "cache-control": "public, max-age=31536000" } })));
    } else {
      const c = await cache.match(LAST_GOOD);
      if (c) {
        body = await c.text();
        src = "cache";
      } else if (env.app_ads) {
        body = await env.app_ads.get("app-ads.txt");
        src = "kv";
      }
    }
    if (!body) return new Response("temporarily unavailable", { status: 503 });
    return new Response(request.method === "HEAD" ? null : body, {
      headers: {
        "content-type": "text/plain; charset=utf-8",
        "cache-control": "public, max-age=300",
        "x-app-ads-source": src,
      },
    });
  },
};
