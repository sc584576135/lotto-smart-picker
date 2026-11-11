/* verify_exact.js — 校验复式/胆拖的精确覆盖率公式 */
'use strict';
const L = require('./lotto-core.js');

function comb(n, k) {
  if (k < 0 || k > n) return 0;
  if (k === 0 || k === n) return 1;
  k = Math.min(k, n - k);
  let r = 1;
  for (let i = 1; i <= k; i++) r = r * (n - k + i) / i;
  return Math.round(r);
}

function winByHits(f, b) {
  return Object.prototype.hasOwnProperty.call(L.PRIZE_RULES, f + ',' + b);
}

function exactFuPct(F, B) {
  const TOT = comb(35, 5), TOTB = comb(12, 2);
  const px = [], py = [];
  for (let k = 0; k <= 5; k++) px[k] = comb(F, k) * comb(35 - F, 5 - k) / TOT;
  for (let k = 0; k <= 2; k++) py[k] = comb(B, k) * comb(12 - B, 2 - k) / TOTB;
  let p = 0;
  for (let x = 0; x <= 5; x++) {
    if (!px[x]) continue;
    for (let y = 0; y <= 2; y++) {
      if (!py[y]) continue;
      if (winByHits(Math.min(x, 5), Math.min(y, 2))) p += px[x] * py[y];
    }
  }
  return p * 100;
}

function exactDanPct(dF, tF, dB, tB) {
  const needF = 5 - dF, needB = 2 - dB;
  const restF = 35 - dF - tF, restB = 12 - dB - tB;
  const TOT = comb(35, 5), TOTB = comb(12, 2);
  const pf = [], pb = [];
  for (let a = 0; a <= dF; a++) for (let b = 0; b <= tF; b++) {
    const c = 5 - a - b;
    if (c < 0 || c > restF) continue;
    const w = comb(dF, a) * comb(tF, b) * comb(restF, c) / TOT;
    if (!w) continue;
    pf.push({ w, maxHit: a + Math.min(b, needF) });
  }
  for (let a = 0; a <= dB; a++) for (let b = 0; b <= tB; b++) {
    const c = 2 - a - b;
    if (c < 0 || c > restB) continue;
    const w = comb(dB, a) * comb(tB, b) * comb(restB, c) / TOTB;
    if (!w) continue;
    pb.push({ w, maxHit: a + Math.min(b, needB) });
  }
  let p = 0;
  for (const f of pf) for (const b of pb) {
    if (winByHits(Math.min(f.maxHit, 5), Math.min(b.maxHit, 2))) p += f.w * b.w;
  }
  return p * 100;
}

// 蒙特卡洛对照
function mc(tickets, draws) {
  const rng = L.makeRng(999);
  const FA = [...Array(35).keys()].map(x => x + 1);
  const BA = [...Array(12).keys()].map(x => x + 1);
  let hit = 0;
  for (let d = 0; d < draws; d++) {
    const df = L.sample(FA, 5, rng), db = L.sample(BA, 2, rng);
    for (const t of tickets) if (L.prizeLevel(t[0], t[1], df, db) > 0) { hit++; break; }
  }
  return hit / draws * 100;
}

function buildFu(F, B) {
  const front = [...Array(F).keys()].map(x => x + 1);
  const back = [...Array(B).keys()].map(x => x + 1);
  const fc = [], bc = [], t = [];
  const rec = (s, c) => { if (c.length === 5) { fc.push(c.slice()); return; } for (let i = s; i < front.length; i++) { c.push(front[i]); rec(i + 1, c); c.pop(); } };
  rec(0, []);
  for (let i = 0; i < back.length; i++) for (let j = i + 1; j < back.length; j++) bc.push([back[i], back[j]]);
  for (const f of fc) for (const b of bc) t.push([f, b]);
  return t;
}

function buildDan(danF, tuoF, danB, tuoB) {
  const needF = 5 - danF.length, needB = 2 - danB.length;
  const fc = [], bc = [], t = [];
  const r1 = (s, c) => { if (c.length === needF) { fc.push(c.slice()); return; } for (let i = s; i < tuoF.length; i++) { c.push(tuoF[i]); r1(i + 1, c); c.pop(); } };
  r1(0, []); if (needF === 0) fc.push([]);
  const r2 = (s, c) => { if (c.length === needB) { bc.push(c.slice()); return; } for (let i = s; i < tuoB.length; i++) { c.push(tuoB[i]); r2(i + 1, c); c.pop(); } };
  r2(0, []); if (needB === 0) bc.push([]);
  for (const f of fc) for (const b of bc) t.push([[...danF, ...f].sort((a, b) => a - b), [...danB, ...b].sort((a, b) => a - b)]);
  return t;
}

console.log('=== 复式：精确 vs 蒙特卡洛 ===');
for (const [F, B] of [[6, 2], [7, 2], [8, 3], [10, 4]]) {
  const ex = exactFuPct(F, B);
  const tickets = buildFu(F, B);
  const m = mc(tickets, 60000);
  const diff = Math.abs(ex - m);
  console.log(`前区${F}+后区${B}  ${tickets.length}注  精确 ${ex.toFixed(2)}%  模拟 ${m.toFixed(2)}%  差 ${diff.toFixed(2)}  ${diff < 1.0 ? 'OK' : 'MISMATCH'}`);
}

console.log('\n=== 胆拖：精确 vs 蒙特卡洛 ===');
for (const [dF, tF, dB, tB] of [
  [[3, 15], [1, 7, 12, 20, 25, 30, 33], [5], [1, 7, 9]],
  [[1], [2, 3, 4, 5, 6, 7, 8], [], [1, 2, 3]],
  [[1, 2, 3], [4, 5, 6, 7, 8, 9, 10, 11], [1], [2, 3, 4, 5]],
]) {
  const ex = exactDanPct(dF.length, tF.length, dB.length, tB.length);
  const tickets = buildDan(dF, tF, dB, tB);
  const m = mc(tickets, 40000);
  const diff = Math.abs(ex - m);
  console.log(`胆${dF.length}+拖${tF.length}/胆${dB.length}+拖${tB.length}  ${tickets.length}注  精确 ${ex.toFixed(2)}%  模拟 ${m.toFixed(2)}%  差 ${diff.toFixed(2)}  ${diff < 1.2 ? 'OK' : 'MISMATCH'}`);
}

console.log('\n=== 极端校验 ===');
console.log('全包 35+12:', exactFuPct(35, 12).toFixed(4), '%（应为 100）');
console.log('单注 5+2  :', exactFuPct(5, 2).toFixed(4), '%（应为 6.6705）');
