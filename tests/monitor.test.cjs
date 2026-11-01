const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const core = require("../docs/monitor-core.js");
const fixture = () => {
  const d = JSON.parse(
    fs.readFileSync(
      require("node:path").join(__dirname, "../docs/data.json"),
      "utf8",
    ),
  );
  d.runtime = { at: null, status: "UNCONNECTED" };
  for (const b of d.bots)
    Object.assign(b, { calls: 0, pnl: null, sessions: 0, eligible: false });
  return d;
};
test("complete published registry and truthful empty performance", () => {
  const d = core.validate(fixture());
  assert.equal(d.bots.length, fixture().bots.length);
  assert(d.summary.symbols >= 150);
  assert.equal(
    d.districts.reduce((s, d) => s + d.count, 0),
    d.bots.length,
  );
  assert.equal(d.summary.completed, 0);
  assert.equal(d.summary.pnl, null);
});
test("search matches tickers and strategies with combined filters", () => {
  const d = core.validate(fixture());
  assert(
    core
      .filterBots(d, { query: "NVDA", role: "watcher", zone: "circuit" })
      .some((b) => b.name === "NVDA WATCHER"),
  );
  assert.equal(core.filterBots(d, { query: "COURIER" }).length, 1);
  assert.equal(
    core.filterBots(d, { query: "nonexistent-token-xyz" }).length,
    0,
  );
  assert(
    core.filterBots(d, { book: "swing" }).every((b) => b.hold === "swing"),
  );
});
test("new publication never implies new runner heartbeat", () => {
  const d = core.validate(fixture());
  const now = Date.now();
  d.generatedAt = new Date(now).toISOString();
  assert.equal(core.freshness(d, now).fresh, false);
  d.runtime = { at: new Date(now - 360000).toISOString(), status: "READY" };
  assert.match(core.freshness(d, now).label, /old/);
  d.runtime = {
    at: new Date(now - 30000).toISOString(),
    status: "MARKET_CLOSED",
  };
  assert.equal(core.freshness(d, now).fresh, true);
  d.runtime.status = "NEEDS_DATA";
  assert.equal(core.freshness(d, now).fresh, false);
});
test("rejects corrupt schema, duplicate bots, invalid P/L and unknown districts", () => {
  for (const change of [
    (d) => (d.schemaVersion = 99),
    (d) => d.bots.push(d.bots[0]),
    (d) => (d.bots[0].pnl = Infinity),
    (d) => (d.bots[0].zone = "missing"),
  ]) {
    const d = fixture();
    change(d);
    assert.throws(() => core.validate(d));
  }
});
test("untrusted HTML and summary are not accepted from data", () => {
  const raw = fixture();
  raw.bots[0].perf = "<img src=x onerror=alert(1)>";
  raw.summary.pnl = 999999999;
  raw.summary.bots = 1;
  const d = core.validate(raw);
  assert.equal(d.bots[0].perf, undefined);
  assert.equal(d.summary.pnl, null);
  assert.equal(d.summary.bots, raw.bots.length);
});
test("per-bot productivity uses completed trades, and activity sorts", () => {
  const raw = fixture();
  raw.bots[0].calls = 4;
  raw.bots[0].wins = 3;
  raw.bots[0].events = 10;
  raw.bots[0].lastActivityAt = "2026-10-30T17:00:00Z";
  raw.bots[1].calls = 2;
  raw.bots[1].wins = 2;
  raw.bots[1].lastActivityAt = "2026-10-30T16:00:00Z";
  const d = core.validate(raw);
  assert.equal(d.bots[0].winRate, 75);
  assert.equal(d.bots[0].events, 10);
  assert.equal(d.bots[2].winRate, null);
  assert.equal(core.filterBots(d, {sort: "winrate"})[0].i, 1);
  assert.equal(core.filterBots(d, {sort: "recent"})[0].i, 0);
});
test("negative P/L ranks ahead of unscored bots", () => {
  const d = core.validate(fixture());
  d.bots[0].pnl = -20;
  d.bots[0].calls = 1;
  d.bots[1].pnl = 20;
  d.bots[1].calls = 1;
  assert.deepEqual(
    core
      .filterBots(d, { sort: "pnl" })
      .slice(0, 2)
      .map((b) => b.pnl),
    [20, -20],
  );
});

const cityMap = require('../docs/city-map.js');
test('city draws every registered bot exactly once and all sector controls', () => {
  const d=core.validate(fixture()), svg=cityMap.render(d);
  const ids=[...svg.matchAll(/class="iso-building[^\"]*"[^>]*data-bot="(\d+)"/g)].map(m=>Number(m[1]));
  assert.equal(ids.length,d.bots.length);
  assert.equal(new Set(ids).size,d.bots.length);
  for(const sector of d.districts) assert(svg.includes('aria-label="Open '+sector.label.replaceAll('&','&amp;')+'"'));
  assert(!/NaN|Infinity/.test(svg));
});
test('every focused sector contains its full bot membership and fitted geometry', () => {
  const d=core.validate(fixture());
  for(const sector of d.districts) {
    const rows=d.bots.filter(b=>b.zone===sector.id),svg=cityMap.render(d,sector.id);
    assert.equal([...svg.matchAll(/class="iso-building/g)].length,rows.length);
    const [x,y,w,h]=cityMap.bounds(d,sector.id);
    for(const b of rows) for(const [px,py] of cityMap.box(b.x,b.z,b.w,Math.min(b.h*.5,32)).top) {
      assert(px>=x && px<=x+w && py>=y && py<=y+h);
    }
    for(const b of d.bots.filter(b=>b.zone!==sector.id)) assert(!svg.includes('data-bot="'+b.i+'"'));
  }
});
test('city escapes source labels and does not require a remote renderer', () => {
  const d=core.validate(fixture());
  d.bots[0].name='<img src=x onerror=alert(1)>';
  d.districts[0].label='<script>test</script>';
  const svg=cityMap.render(d);
  assert(!svg.includes('<img'));assert(!svg.includes('<script>'));
  assert(svg.includes('&lt;img'));assert(!svg.includes('https://'));
});
