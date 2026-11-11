/* ============================================================
 * lotto-data.js — 数据层
 *   · 官方开奖数据获取（体彩官方接口，免 key）
 *   · 选号记录本地持久化（localStorage）
 *   · 中奖核对
 * ============================================================ */
'use strict';

(function (global) {

  // ---------- 存储键 ----------
  const K_RECORDS = 'lotto_records';   // 历史开奖（遗漏分层用）
  const K_SAVED = 'lotto_saved';      // 用户保存的选号组
  const K_CFG = 'lotto_cfg';          // 配置

  // ---------- 官方接口 ----------
  // gameNo=85 为超级大乐透；该接口无需 appkey
  const API = 'https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry'
            + '?gameNo=85&provinceId=0&isVerify=1&pageSize=__N__&pageNo=1';

  function apiUrl(n) { return API.replace('__N__', String(Math.max(1, Math.min(100, n)))); }

  // 统一取数：APP 内走原生桥，浏览器内走 fetch
  function httpGet(url) {
    if (global.NativeNet && typeof global.NativeNet.fetch === 'function') {
      const raw = global.NativeNet.fetch(url);
      return Promise.resolve(raw);
    }
    return fetch(url, { headers: { 'Accept': 'application/json' } })
      .then(r => {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.text();
      });
  }

  function parseDraw(json) {
    let o;
    try { o = JSON.parse(json); } catch { throw new Error('返回内容不是 JSON'); }
    if (o && o.__error) throw new Error(o.__error);
    const list = o && o.value && o.value.list;
    if (!Array.isArray(list)) throw new Error('接口返回结构异常');

    return list.map(it => {
      const nums = String(it.lotteryDrawResult || '').trim().split(/\s+/).map(Number);
      if (nums.length < 7 || nums.some(isNaN)) return null;
      return {
        period: String(it.lotteryDrawNum || ''),
        date: String(it.lotteryDrawTime || ''),
        front: nums.slice(0, 5),
        back: nums.slice(5, 7)
      };
    }).filter(Boolean);
  }

  // 拉取最近 n 期并写入本地
  function fetchDraws(n) {
    return httpGet(apiUrl(n)).then(txt => {
      const recs = parseDraw(txt);
      if (!recs.length) throw new Error('没有解析到有效开奖记录');
      saveRecords(recs);
      return recs;
    });
  }

  // ---------- 历史开奖记录 ----------
  function loadRecords() {
    try {
      const raw = localStorage.getItem(K_RECORDS);
      if (!raw) return [];
      const arr = JSON.parse(raw);
      return Array.isArray(arr) ? arr : [];
    } catch { return []; }
  }

  // 合并去重，按期号倒序（records[0] 必须是最新一期）
  function saveRecords(recs) {
    const old = loadRecords();
    const map = {};
    for (const r of old) if (r && r.period) map[r.period] = r;
    for (const r of recs) if (r && r.period) map[r.period] = r;
    const merged = Object.keys(map).map(k => map[k])
      .sort((a, b) => String(b.period).localeCompare(String(a.period)));
    localStorage.setItem(K_RECORDS, JSON.stringify(merged));
    return merged;
  }

  // 手动录入一期（离线也能用）
  function addRecord(period, date, front, back) {
    const rec = { period: String(period), date: String(date || ''), front, back };
    saveRecords([rec]);
    return rec;
  }

  // ---------- 选号记录 ----------
  // 一组 = {id, ts, mode, tickets:[[front,back],...], extra}
  function loadSaved() {
    try {
      const raw = localStorage.getItem(K_SAVED);
      if (!raw) return [];
      const arr = JSON.parse(raw);
      return Array.isArray(arr) ? arr : [];
    } catch { return []; }
  }

  function persistSaved(arr) {
    localStorage.setItem(K_SAVED, JSON.stringify(arr));
  }

  function saveGroup(group) {
    const arr = loadSaved();
    arr.unshift(group);
    // 只保留最近 200 组，避免 localStorage 撑爆
    persistSaved(arr.slice(0, 200));
    return arr.length;
  }

  function removeGroup(id) {
    const arr = loadSaved().filter(g => g.id !== id);
    persistSaved(arr);
    return arr;
  }

  function clearSaved() {
    localStorage.removeItem(K_SAVED);
  }

  // ---------- 中奖核对 ----------
  // 返回 {level, name, money, hitFront, hitBack, cond}
  function checkTicket(front, back, drawFront, drawBack) {
    const info = LOTTO.prizeInfo(front, back, drawFront, drawBack);
    const hf = LOTTO.hitCount(front, drawFront);
    const hb = LOTTO.hitCount(back, drawBack);
    if (!info) return { level: 0, name: '未中奖', money: 0, hitFront: hf, hitBack: hb, cond: `${hf}+${hb}` };
    return {
      level: LOTTO.prizeLevel(front, back, drawFront, drawBack),
      name: info[0],
      money: info[1] === null ? -1 : info[1],   // -1 表示浮动奖金（一/二等奖）
      hitFront: hf,
      hitBack: hb,
      cond: info[2]
    };
  }

  // 一组号码对某期开奖的整体核对
  function checkGroup(tickets, draw) {
    const rows = tickets.map((t, i) => {
      const r = checkTicket(t[0], t[1], draw.front, draw.back);
      r.idx = i + 1;
      r.front = t[0];
      r.back = t[1];
      return r;
    });
    const win = rows.filter(r => r.level > 0);
    const fixed = win.reduce((s, r) => s + (r.money > 0 ? r.money : 0), 0);
    const floating = win.filter(r => r.money === -1).length;
    return {
      rows,
      winCount: win.length,
      total: tickets.length,
      money: fixed,
      floating,
      best: win.length ? win.reduce((a, b) => (a.level < b.level ? a : b)) : null
    };
  }

  // ---------- 数据导出 ----------
  // 导出全部本地数据为 JSON 文本（不含 API Key）；返回 JSON 字符串
  function exportAll() {
    const data = {
      app: '大乐透智能选号',
      version: 'v1.1',
      exportedAt: new Date().toISOString(),
      savedGroups: loadSaved(),
      drawRecords: loadRecords()
    };
    return JSON.stringify(data, null, 2);
  }

  function downloadExport(json, filename) {
    // 1. APP 内：原生桥写系统下载目录
    if (global.NativeNet && typeof global.NativeNet.saveFile === 'function') {
      const res = global.NativeNet.saveFile(filename, json);
      try {
        const o = JSON.parse(res);
        if (o && o.ok) return { ok: true, path: o.ok };
        return { ok: false, error: o && o.__error || '保存失败' };
      } catch { return { ok: false, error: '原生桥返回异常' }; }
    }
    // 2. 浏览器：Blob 下载
    try {
      const blob = new Blob([json], { type: 'application/json' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(a.href), 2000);
      return { ok: true, path: filename };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  global.LOTTO_DATA = {
    K_RECORDS, K_SAVED, K_CFG,
    fetchDraws, parseDraw, apiUrl,
    loadRecords, saveRecords, addRecord,
    loadSaved, saveGroup, removeGroup, clearSaved,
    checkTicket, checkGroup,
    exportAll, downloadExport
  };

})(typeof window !== 'undefined' ? window : globalThis);
