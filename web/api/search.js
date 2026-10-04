const APIFY_URL = "https://api.apify.com/v2/actors/searchapi~google-images-scraper/run-sync-get-dataset-items";

const OFFICIAL = {
  "VAILLANT": ["vaillant.sk", "vaillant.com"],
  "STIEBEL ELTRON": ["stiebel-eltron.sk", "stiebel-eltron.com"],
  "ARISTON": ["ariston.com"],
  "DRAŽICE": ["dzd.cz", "drazice.cz"],
  "DRAZICE": ["dzd.cz", "drazice.cz"],
  "CLAGE": ["clage.com"],
  "HAKL": ["hakl.sk"],
  "MORA": ["mora.sk", "mora.cz"],
  "TESY": ["tesy.com"],
  "CONCEPT": ["my-concept.sk", "my-concept.cz"]
};

function normalizeHost(value = "") {
  try {
    if (/^https?:\/\//i.test(value)) return new URL(value).hostname.toLowerCase().replace(/^www\./, "");
  } catch {}
  return String(value).toLowerCase().replace(/^www\./, "").split(":")[0];
}

function hostMatches(host, domains) {
  host = normalizeHost(host);
  return domains.some(d => host === d || host.endsWith("." + d));
}

function brandFromName(name = "") {
  const up = name.toUpperCase();
  const brands = Object.keys(OFFICIAL).sort((a,b) => b.length-a.length);
  return brands.find(b => up.startsWith(b + " ") || up === b) || (name.split(/\s+/)[0] || "").toUpperCase();
}

function queryFor(product) {
  const brand = product.brand || brandFromName(product.name);
  const domains = OFFICIAL[brand] || [];
  const shortName = product.name.split(/\s+/).slice(0, 8).join(" ");
  return domains.length
    ? `${product.code} ${shortName} site:${domains[0]}`
    : `${product.code} ${shortName}`;
}

function candidateScore(product, item) {
  const brand = product.brand || brandFromName(product.name);
  const domains = OFFICIAL[brand] || [];
  const host = item.hostPageDomain || item.sourceDomain || item.domain || "";
  const official = domains.length && hostMatches(host, domains) ? 1000000000 : 0;
  const text = [item.title, item.altText, item.sourceName].filter(Boolean).join(" ").toLowerCase();
  const code = String(product.code || "").toLowerCase();
  const codeMatch = code && text.includes(code) ? 10000000 : 0;
  const tokens = product.name.toLowerCase().split(/[^a-z0-9]+/).filter(t => t.length >= 3);
  const tokenScore = tokens.reduce((n,t) => n + (text.includes(t) ? 1000 : 0), 0);
  const pixels = Number(item.sizePixels || 0) || Number(item.width || 0) * Number(item.height || 0);
  return official + codeMatch + tokenScore + pixels;
}

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({error:"POST only"});

  try {
    const { products, token } = req.body || {};
    if (!Array.isArray(products) || !products.length) {
      return res.status(400).json({error:"Chýba zoznam produktov."});
    }
    const apiToken = process.env.APIFY_TOKEN || token;
    if (!apiToken) return res.status(400).json({error:"Chýba Apify API token."});

    const limited = products.slice(0, 20).map(p => ({
      code: String(p.code || "").trim(),
      name: String(p.name || "").trim(),
      brand: p.brand || brandFromName(String(p.name || ""))
    })).filter(p => p.code && p.name);

    const queries = limited.map(queryFor);
    const response = await fetch(APIFY_URL + "?token=" + encodeURIComponent(apiToken), {
      method:"POST",
      headers:{"content-type":"application/json"},
      body:JSON.stringify({
        mode:"batch",
        queries,
        maxItems: Math.max(queries.length * 8, 8),
        maxConcurrency:2
      })
    });

    const raw = await response.text();
    if (!response.ok) {
      return res.status(response.status).json({error:`Apify ${response.status}: ${raw.slice(0,1200)}`});
    }

    let items;
    try { items = JSON.parse(raw); }
    catch { return res.status(502).json({error:"Apify vrátilo neplatnú JSON odpoveď."}); }

    const byQuery = new Map(queries.map(q => [q, []]));
    for (const item of Array.isArray(items) ? items : []) {
      const q = item.query || item.searchQuery;
      if (byQuery.has(q)) byQuery.get(q).push(item);
    }

    const results = limited.map(product => {
      const q = queryFor(product);
      const candidates = (byQuery.get(q) || []).sort((a,b) => candidateScore(product,b)-candidateScore(product,a));
      const domains = OFFICIAL[product.brand] || [];
      const verified = candidates.filter(item => {
        if (!domains.length) return true;
        const host = item.hostPageDomain || item.sourceDomain || item.domain || "";
        return hostMatches(host, domains);
      });
      const chosen = verified.find(item => item.imageUrl || item.originalUrl || item.url) || null;
      return {
        ...product,
        query:q,
        status: chosen ? "OK" : "NENAJDENE",
        imageUrl: chosen ? (chosen.imageUrl || chosen.originalUrl || chosen.url) : "",
        hostPageUrl: chosen ? (chosen.hostPageUrl || chosen.sourceUrl || "") : "",
        hostPageDomain: chosen ? (chosen.hostPageDomain || chosen.sourceDomain || chosen.domain || "") : "",
        title: chosen ? (chosen.title || chosen.altText || "") : "",
        width: chosen ? Number(chosen.width || 0) : 0,
        height: chosen ? Number(chosen.height || 0) : 0,
        candidateCount: candidates.length
      };
    });

    res.status(200).json({results});
  } catch (e) {
    res.status(500).json({error:e?.message || String(e)});
  }
}
