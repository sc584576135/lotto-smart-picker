/* ============================================================
 * lotto-core.js — 大乐透核心算法（JS 移植，与 Python 版严格一致）
 * 无依赖，可在浏览器/WebView 中运行
 * ============================================================ */
'use strict';

const LOTTO = (function () {

  // ---------- 组合数学常量 ----------
  function comb(n, k) {
    if (k < 0 || k > n) return 0;
    if (k === 0 || k === n) return 1;
    k = Math.min(k, n - k);
    let r = 1;
    for (let i = 1; i <= k; i++) r = r * (n - k + i) / i;
    return Math.round(r);
  }

  const C_FRONT = comb(35, 5);            // 324632
  const C_BACK = comb(12, 2);             // 66
  const TOTAL_COMBOS = C_FRONT * C_BACK;  // 21425712

  // 官方奖级结构：前区命中数, 后区命中数
  const WIN_PATTERNS = [
    [5, 2], [5, 1], [5, 0],
    [4, 2], [4, 1],
    [3, 2], [4, 0],
    [2, 2], [3, 1],
    [3, 0], [1, 2], [2, 1], [0, 2]
  ];

  let WINNING_COMBOS = 0;
  for (const [f, b] of WIN_PATTERNS) {
    WINNING_COMBOS += comb(5, f) * comb(30, 5 - f) * comb(2, b) * comb(10, 2 - b);
  }
  // = 1429197

  const P_SINGLE_WIN = WINNING_COMBOS / TOTAL_COMBOS;   // 6.6705%
  const P_FIRST_PRIZE = 1 / TOTAL_COMBOS;

  // ---------- 中奖判定 ----------
  function hitCount(a, b) {
    const sa = new Set(a);
    let n = 0;
    for (const x of b) if (sa.has(x)) n++;
    return n;
  }

  function isWinning(front, back, drawFront, drawBack) {
    return prizeLevel(front, back, drawFront, drawBack) > 0;
  }

  // 奖级表：与 Python 版 PRIZE_RULES 逐项一致（前区命中, 后区命中）
  const PRIZE_RULES = {
    '5,2': ['一等奖', null, '5+2'],
    '5,1': ['二等奖', null, '5+1'],
    '5,0': ['三等奖', 10000, '5+0'],
    '4,2': ['四等奖', 3000, '4+2'],
    '3,2': ['四等奖', 200, '3+2'],
    '4,1': ['五等奖', 300, '4+1'],
    '4,0': ['五等奖', 100, '4+0'],
    '3,1': ['六等奖', 15, '3+1'],
    '2,2': ['六等奖', 15, '2+2'],
    '3,0': ['七等奖', 5, '3+0'],
    '2,1': ['七等奖', 5, '2+1'],
    '1,2': ['七等奖', 5, '1+2'],
    '0,2': ['七等奖', 5, '0+2']
  };

  function prizeLevel(front, back, drawFront, drawBack) {
    const f = hitCount(front, drawFront);
    const b = hitCount(back, drawBack);
    const hit = PRIZE_RULES[`${f},${b}`];
    if (!hit) return 0;
    // 返回奖级序号 1..7（一~七等奖），0 表示未中奖
    const nameMap = { '一等奖': 1, '二等奖': 2, '三等奖': 3, '四等奖': 4, '五等奖': 5, '六等奖': 6, '七等奖': 7 };
    return nameMap[hit[0]] || 0;
  }

  function prizeInfo(front, back, drawFront, drawBack) {
    const f = hitCount(front, drawFront);
    const b = hitCount(back, drawBack);
    return PRIZE_RULES[`${f},${b}`] || null;
  }

  // ---------- 概率 ----------
  function probAtLeastOne(n) {
    return 1 - Math.pow(1 - P_SINGLE_WIN, n);
  }

  function ticketsForTarget(target) {
    if (target <= 0) return 1;
    if (target >= 1) return TOTAL_COMBOS;
    return Math.ceil(Math.log(1 - target) / Math.log(1 - P_SINGLE_WIN));
  }

  // ---------- 重叠代价 ----------
  const FRONT_W = 3.0, BACK_W = 2.0;

  function overlapCost(t1, t2) {
    const f1 = new Set(t1[0]), f2 = new Set(t2[0]);
    let fCommon = 0;
    for (const x of f2) if (f1.has(x)) fCommon++;
    const b1 = new Set(t1[1]), b2 = new Set(t2[1]);
    let bCommon = 0;
    for (const x of b2) if (b1.has(x)) bCommon++;
    return FRONT_W * fCommon + BACK_W * bCommon;
  }

  function totalOverlap(tickets) {
    let s = 0;
    for (let i = 0; i < tickets.length; i++)
      for (let j = i + 1; j < tickets.length; j++)
        s += overlapCost(tickets[i], tickets[j]);
    return s;
  }

  // ---------- 覆盖率优化（贪心最小重叠） ----------
  // 参数顺序兼容 Python 版：optimize(candidates, count, sampleCap, seed)
  // 也支持 optimize(candidates, count, seed) —— 第三参数为数字且 <= 1e6 时视为 seed
  function optimize(candidates, count, sampleCap, seed) {
    if (sampleCap === null || sampleCap === undefined) sampleCap = 4000;
    // 兼容 (candidates, count, seed) 调用形式
    if (typeof sampleCap === 'number' && seed === undefined && sampleCap <= 1e6) {
      seed = sampleCap;
      sampleCap = 4000;
    }
    if (typeof sampleCap !== 'number' || sampleCap < 1) sampleCap = 4000;
    const rng = makeRng(seed === undefined ? null : seed);
    // 去重 + 统一为 [front, back] 数组
    const key = t => JSON.stringify([t[0].slice().sort((a, b) => a - b), t[1].slice().sort((a, b) => a - b)]);
    const seen = new Set();
    let pool = [];
    for (const c of candidates) {
      const k = key(c);
      if (!seen.has(k)) { seen.add(k); pool.push([c[0].slice(), c[1].slice()]); }
    }
    if (pool.length <= count) return pool;
    if (pool.length > sampleCap) pool = sampleArr(pool, sampleCap, rng);

    const chosen = [pool.shift()];
    while (chosen.length < count && pool.length) {
      let bestIdx = 0, bestCost = Infinity;
      for (let i = 0; i < pool.length; i++) {
        let cost = 0;
        for (let j = 0; j < chosen.length; j++) cost += overlapCost(pool[i], chosen[j]);
        if (cost < bestCost) { bestCost = cost; bestIdx = i; if (cost === 0) break; }
      }
      chosen.push(pool.splice(bestIdx, 1)[0]);
    }
    return chosen;
  }

  // ---------- 覆盖率评分（按 30000 次模拟校准） ----------
  function coverageScore(tickets) {
    const n = tickets.length;
    if (n === 0) return 0;
    if (n === 1) return P_SINGLE_WIN;
    const base = probAtLeastOne(n);
    const worst = totalOverlap(new Array(n).fill(tickets[0]));
    if (worst <= 0) return base;
    const ratio = Math.min(1, totalOverlap(tickets) / worst);
    let optDegree = Math.max(0, 0.155 - ratio) / 0.155;
    if (n < 4) optDegree = 0;
    const peak = 9.0 * (1 - Math.pow((n - 17.0) / 26.0, 2));
    const boost = optDegree * Math.max(0, peak) / 100;
    return Math.min(base + boost, 0.999);
  }

  // ---------- 随机数（可复现） ----------
  function makeRng(seed) {
    if (seed === null || seed === undefined) return { next: Math.random };
    let s = seed >>> 0 || 1;
    return {
      next() { s ^= s << 13; s >>>= 0; s ^= s >> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; }
    };
  }

  function randInt(rng, n) { return Math.floor(rng.next() * n); }

  function sampleArr(arr, k, rng) {
    const a = arr.slice();
    for (let i = 0; i < k; i++) {
      const j = i + randInt(rng, a.length - i);
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a.slice(0, k);
  }

  function sample(arr, k, rng) { return sampleArr(arr, k, rng); }

  // ---------- 导出 ----------
  return {
    comb, C_FRONT, C_BACK, TOTAL_COMBOS, WIN_PATTERNS, WINNING_COMBOS,
    P_SINGLE_WIN, P_FIRST_PRIZE,
    hitCount, isWinning, prizeLevel, prizeInfo, PRIZE_RULES,
    probAtLeastOne, ticketsForTarget,
    overlapCost, totalOverlap, optimize, coverageScore,
    makeRng, sample, randInt
  };
})();

if (typeof module !== 'undefined' && module.exports) module.exports = LOTTO;
