/* measure_js.js — 用 JS 引擎实测覆盖率（蒙特卡洛） */
'use strict';
const L = require('./lotto-core.js');
const R = require('./lotto-rules.js');

// 构造历史记录（用于分层加权）
function makeRecs(n) {
  const recs = [];
  for (let i = 0; i < n; i++) {
    const f = [...Array(35).keys()].map(x => x + 1).sort(() => Math.random() - 0.5).slice(0, 5).sort((a, b) => a - b);
    const b = [...Array(12).keys()].map(x => x + 1).sort(() => Math.random() - 0.5).slice(0, 2).sort((a, b) => a - b);
    recs.push({ front: f, back: b });
  }
  return recs;
}

function buildTickets(count, recs) {
  const gen = new R.Generator({ records: recs });
  const pool = [];
  const seen = new Set();
  const candTarget = Math.max(count * 30, 300);
  let tries = candTarget * 12;
  while (pool.length < candTarget && tries > 0) {
    tries--;
    let t;
    try { t = gen.generate(); } catch (e) { break; }
    const k = JSON.stringify([t.front, t.back]);
    if (!seen.has(k)) { seen.add(k); pool.push([t.front, t.back]); }
  }
  if (pool.length <= count) return pool;
  return L.optimize(pool, count);
}

// 随机一注（用于对照）
function randTicket(rng) {
  return [L.sample([...Array(35).keys()].map(x => x + 1), 5, rng).sort((a, b) => a - b),
          L.sample([...Array(12).keys()].map(x => x + 1), 2, rng).sort((a, b) => a - b)];
}

function measure(tickets, draws, rng) {
  let hit = 0;
  for (let d = 0; d < draws; d++) {
    const df = L.sample([...Array(35).keys()].map(x => x + 1), 5, rng);
    const db = L.sample([...Array(12).keys()].map(x => x + 1), 2, rng);
    let win = false;
    for (const [f, b] of tickets) {
      if (L.prizeLevel(f, b, df, db) > 0) { win = true; break; }
    }
    if (win) hit++;
  }
  return hit / draws;
}

const SIZES = [1, 2, 3, 5, 8, 10, 15, 17, 20, 25, 30, 34, 40, 50];
const DRAWS = 40000;
const REPS = 5;

const rng = L.makeRng(12345);
const out = {};

for (const n of SIZES) {
  const recs = makeRecs(50);
  const vals = [];
  for (let r = 0; r < REPS; r++) {
    const tickets = buildTickets(n, recs);
    vals.push(measure(tickets, DRAWS / REPS, rng));
  }
  const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
  const theo = (1 - Math.pow(1 - L.P_SINGLE_WIN, n)) * 100;
  out[n] = { mean: +(mean * 100).toFixed(1), theo: +theo.toFixed(1) };
  console.log(`n=${String(n).padStart(2)}  实测 ${(mean*100).toFixed(1)}%   独立理论 ${theo.toFixed(1)}%   提升 ${(mean*100-theo).toFixed(1)}%`);
}

console.log('\n--- 对照：随机选号 ---');
for (const n of [10, 34]) {
  const vals = [];
  for (let r = 0; r < REPS; r++) {
    const t = [];
    for (let i = 0; i < n; i++) t.push(randTicket(rng));
    vals.push(measure(t, DRAWS / REPS, rng));
  }
  console.log(`n=${n} 随机 ${(vals.reduce((a,b)=>a+b,0)/vals.length*100).toFixed(1)}%`);
}

require('fs').writeFileSync('measured_js.json', JSON.stringify(out, null, 2));
console.log('\n已写入 measured_js.json');
