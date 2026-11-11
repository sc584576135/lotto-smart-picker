/* ============================================================
 * lotto-ai.js — AI 智能选号（对应桌面版 lotto_ai.py）
 *   OpenAI 兼容 chat 接口，可选功能，无 Key 自动降级
 * ============================================================ */
'use strict';

(function (global) {

  // 兼容的免费/低价模型清单（与桌面版 PROVIDER_PRESETS 一致）
  const PROVIDER_PRESETS = {
    'SiliconFlow(硅基流动)': { base_url: 'https://api.siliconflow.cn/v1', model: 'deepseek-ai/DeepSeek-V3', free: true },
    'DeepSeek':              { base_url: 'https://api.deepseek.com/v1',       model: 'deepseek-chat',          free: false },
    '智谱GLM':               { base_url: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4-flash',       free: true },
    '阿里百炼Qwen':          { base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus', free: false },
    'OpenRouter(免费)':      { base_url: 'https://openrouter.ai/api/v1',     model: 'meta-llama/llama-3.1-8b-instruct:free', free: true }
  };

  const K_AI = 'lotto_ai_cfg';

  function defaultCfg() {
    return {
      enabled: false,
      provider: 'SiliconFlow(硅基流动)',
      base_url: PROVIDER_PRESETS['SiliconFlow(硅基流动)'].base_url,
      model: PROVIDER_PRESETS['SiliconFlow(硅基流动)'].model,
      api_key: '',
      timeout: 30000
    };
  }

  function loadCfg() {
    try {
      const raw = localStorage.getItem(K_AI);
      if (!raw) return defaultCfg();
      const o = JSON.parse(raw);
      return Object.assign(defaultCfg(), o);
    } catch { return defaultCfg(); }
  }

  function saveCfg(cfg) {
    localStorage.setItem(K_AI, JSON.stringify(cfg));
  }

  // 统一取数：APP 内走原生桥，浏览器内走 fetch
  function httpPost(url, headers, body, timeout) {
    if (global.NativeNet && typeof global.NativeNet.post === 'function') {
      const raw = global.NativeNet.post(url, JSON.stringify(headers), body);
      return Promise.resolve(raw);
    }
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeout || 30000);
    return fetch(url, {
      method: 'POST',
      headers: headers,
      body: body,
      signal: ctrl.signal
    }).then(r => {
      clearTimeout(timer);
      return r.text();
    }).catch(e => {
      clearTimeout(timer);
      throw e;
    });
  }

  // 调用一次 chat 接口，返回 {ok, text}
  function chatOnce(cfg, prompt) {
    if (!cfg || !cfg.enabled || !cfg.api_key) {
      return Promise.resolve({ ok: false, text: '', err: 'AI 未启用或未填 API Key' });
    }
    const url = cfg.base_url.replace(/\/+$/, '') + '/chat/completions';
    const headers = {
      'Authorization': 'Bearer ' + cfg.api_key,
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    };
    const body = JSON.stringify({
      model: cfg.model,
      messages: [
        { role: 'system', content: '你是资深彩票数据分析助手，只输出号码，不解释。' },
        { role: 'user', content: prompt }
      ],
      temperature: 0.9,
      max_tokens: 300
    });

    return httpPost(url, headers, body, cfg.timeout || 30000)
      .then(txt => {
        let data;
        try { data = JSON.parse(txt); }
        catch { return { ok: false, text: '', err: '返回内容不是 JSON' }; }
        if (data && data.error) {
          return { ok: false, text: '', err: '接口错误：' + (data.error.message || data.error.code || '未知') };
        }
        const content = data && data.choices && data.choices[0] && data.choices[0].message
          ? data.choices[0].message.content : '';
        return { ok: !!content, text: content || '', err: content ? '' : '模型无输出' };
      })
      .catch(e => ({ ok: false, text: '', err: '网络错误：' + (e.message || e) }));
  }

  // 构造提示词（与桌面版 _llm_assist 一致：热号 + 冷号 + 上一组预测）
  function buildPrompt(records, lastTicket) {
    const recent = records.slice(0, 20);
    const hot = {};
    recent.forEach(r => r.front.forEach(n => { hot[n] = (hot[n] || 0) + 1; }));
    const hotArr = Object.keys(hot).map(Number).sort((a, b) => hot[b] - hot[a]).slice(0, 8);
    const hotStr = hotArr.map(n => n + ':' + hot[n]).join(' ');
    const cold = [];
    for (let n = 1; n <= 35; n++) if (!hot[n]) { cold.push(n); if (cold.length >= 8) break; }

    let lastLine = '';
    if (lastTicket) {
      lastLine = `上一组预测：${lastTicket[0].join(' ')} + ${lastTicket[1].join(' ')}\n`;
    }
    return `请仅输出5个1-35的前区号码和2个1-12的后区号码，共一组，用空格隔开（格式：前区 后区）。\n` +
           `参考最近热号(近20期出现次数)：${hotStr}\n` +
           `冷号：${cold.join(' ')}\n` + lastLine;
  }

  // 从模型输出提炼号码（兼容"前区：02 12 …后区：07 08"等带标签格式）
  function extractNumbers(text) {
    if (!text) return [];
    const nums = [];
    const tokens = String(text).split(/[^0-9]+/);
    for (const t of tokens) {
      if (!t) continue;
      // 限制每个数字串长度，避免把日期/大数误当号码
      const n = parseInt(t, 10);
      if (n >= 1 && n <= 100 && String(n).length <= 2) nums.push(n);
    }
    return nums;
  }

  // 结构化解析：识别"后区"标签分段；无标签则按顺序前 5 后 2（与桌面版行为一致）
  function parseResult(text) {
    const raw = String(text || '');
    const m = raw.match(/后区[：:]\s*/);
    let frontNums, backNums;
    if (m) {
      frontNums = extractNumbers(raw.slice(0, m.index));
      backNums = extractNumbers(raw.slice(m.index + m[0].length));
    } else {
      const all = extractNumbers(raw);
      frontNums = all.slice(0, 5);
      backNums = all.slice(5, 7);
    }
    return {
      front: validateNumbers(frontNums, 1, 35, 5),
      back: validateNumbers(backNums, 1, 12, 2)
    };
  }

  // 去重、限界、截取（与桌面版 validate_numbers 一致）
  function validateNumbers(nums, low, high, count) {
    const result = [];
    for (const n of nums) {
      if (n >= low && n <= high && result.indexOf(n) === -1) result.push(n);
      if (result.length >= count) break;
    }
    for (let n = low; n <= high && result.length < count; n++) {
      if (result.indexOf(n) === -1) result.push(n);
    }
    return result.sort((a, b) => a - b).slice(0, count);
  }

  global.LOTTO_AI = {
    PROVIDER_PRESETS,
    loadCfg, saveCfg,
    chatOnce, buildPrompt, extractNumbers, parseResult, validateNumbers
  };

})(typeof window !== 'undefined' ? window : globalThis);
