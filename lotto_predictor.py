# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import requests
import pandas as pd
import os
import random
import datetime
import json
import threading
import re
import sqlite3
import pickle
import hashlib
import numpy as np
from collections import Counter
from math import comb
import shutil
import sys

from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

import lotto_core as core
import lotto_ai as lai
import lotto_coverage as cov

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'WenQuanYi Micro Hei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================
# 资源路径处理
# ============================================================
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# ============================================================
# 全局配置
# ============================================================
DB_PATH = 'lottery_data.db'
MODEL_PATH = 'ai_model.pkl'
VERSION = "v7.7"
UNIT_PRICE = 2  # 大乐透单注 2 元

# 联网取数配置（可在 lottery_servers.json 中覆盖，无需重新打包）
SERVER_CONFIG_FILE = 'lottery_servers.json'
DEFAULT_JISU_APPKEY = "54c158c4a47f314c"  # 极速数据免费 key，可在 json 里替换

COLORS = {
    "bg_main": "#F5F0EB",
    "bg_top": "#E8E0D5",
    "bg_card": "#FFFFFF",
    "bg_predict": "#2C3E50",
    "text_dark": "#3E3E3E",
    "text_light": "#FFFFFF",
    "accent_blue": "#6C9BCF",
    "accent_green": "#8FBC8F",
    "accent_coral": "#E8A87C",
    "accent_pink": "#D4A5A5",
    "accent_purple": "#B8A9C9",
    "border": "#D5CFC7",
}

DEFAULT_SERVERS = [
    {
        "name": "极速数据API（推荐）",
        "url": "https://api.jisuapi.com/caipiao/history",
        "params": {"appkey": DEFAULT_JISU_APPKEY, "caipiaoid": "14", "issueno": "", "start": "0", "num": "20"},
        "method": "GET", "type": "jisuapi"
    }
]


def load_servers():
    """读取 lottery_servers.json；不存在则用默认值并生成一份供用户修改。"""
    try:
        if os.path.exists(SERVER_CONFIG_FILE):
            with open(SERVER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                return data
    except Exception as e:
        print(f"[servers] 配置读取失败，使用默认值：{e}")
    # 首次运行：写出模板，方便用户改 appkey 而无需重新打包
    try:
        with open(SERVER_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_SERVERS, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[servers] 模板写入失败：{e}")
    return DEFAULT_SERVERS[:]

PAIR_MAP = {
    1: [4], 2: [8], 3: [6], 4: [1, 7], 5: [10],
    6: [3, 9], 7: [4], 8: [2], 9: [6], 10: [5],
    11: [14], 12: [18], 13: [16], 14: [11, 17], 15: [20],
    16: [13, 19], 17: [14], 18: [12], 19: [16], 20: [15],
    21: [24], 22: [28], 23: [16], 24: [21, 27], 25: [30],
    26: [23, 29], 27: [24], 28: [22], 29: [26], 30: [25],
    31: [34], 32: [35], 33: [33], 34: [31], 35: [32]
}

FRONT_RANGE = range(1, 36)
BACK_RANGE = range(1, 13)
ZONES = [list(range(1,13)), list(range(13,25)), list(range(25,36))]
PRIMES = {2,3,5,7,11,13,17,19,23,29,31}

PRIZE_RULES = {
    (5, 2): ("一等奖", "浮动", "5+2"),
    (5, 1): ("二等奖", "浮动", "5+1"),
    (5, 0): ("三等奖", 10000, "5+0"),
    (4, 2): ("四等奖", 3000, "4+2"),
    (3, 2): ("四等奖", 200, "3+2"),
    (4, 1): ("五等奖", 300, "4+1"),
    (4, 0): ("五等奖", 100, "4+0"),
    (3, 1): ("六等奖", 15, "3+1"),
    (2, 2): ("六等奖", 15, "2+2"),
    (3, 0): ("七等奖", 5, "3+0"),
    (2, 1): ("七等奖", 5, "2+1"),
    (1, 2): ("七等奖", 5, "1+2"),
    (0, 2): ("七等奖", 5, "0+2"),
}

# ============================================================
# 数据库
# ============================================================
class Database:
    _instance = None
    _lock = threading.Lock()
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
                    cls._instance.cursor = cls._instance.conn.cursor()
        return cls._instance
    def execute(self, query, params=None):
        with self._lock:
            if params: self.cursor.execute(query, params)
            else: self.cursor.execute(query)
            self.conn.commit()
            return self.cursor
    def fetchone(self, query, params=None):
        with self._lock:
            if params: self.cursor.execute(query, params)
            else: self.cursor.execute(query)
            return self.cursor.fetchone()
    def fetchall(self, query, params=None):
        with self._lock:
            if params: self.cursor.execute(query, params)
            else: self.cursor.execute(query)
            return self.cursor.fetchall()

def get_db(): return Database()

def hash_password(password, salt):
    """加盐 PBKDF2-HMAC-SHA256 口令哈希（2025 年起不应再裸用 SHA-256）。"""
    try:
        return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100_000).hex()
    except Exception:
        return hashlib.sha256((salt + password).encode()).hexdigest()

def init_db():
    db = get_db()
    db.execute("PRAGMA journal_mode=WAL;")
    db.execute('''CREATE TABLE IF NOT EXISTS excel_history (
        period TEXT PRIMARY KEY, date TEXT,
        front1 INTEGER, front2 INTEGER, front3 INTEGER, front4 INTEGER, front5 INTEGER,
        back1 INTEGER, back2 INTEGER)''')
    db.execute('''CREATE TABLE IF NOT EXISTS online_latest (
        period TEXT PRIMARY KEY, date TEXT,
        front1 INTEGER, front2 INTEGER, front3 INTEGER, front4 INTEGER, front5 INTEGER,
        back1 INTEGER, back2 INTEGER)''')
    db.execute('''CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, group_id TEXT, timestamp TEXT,
        predicted_front TEXT, predicted_back TEXT,
        actual_front TEXT, actual_back TEXT,
        is_feedback INTEGER DEFAULT 0, hit_front INTEGER DEFAULT 0, hit_back INTEGER DEFAULT 0)''')
    db.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password_hash TEXT, salt TEXT)''')
    if not any(col[1] == 'salt' for col in db.fetchall("PRAGMA table_info(users)")):
        db.execute("ALTER TABLE users ADD COLUMN salt TEXT")
        # 存量行补默认盐，保持可登录
        db.execute("UPDATE users SET salt='' WHERE salt IS NULL")
    default_salt = os.urandom(16).hex()
    db.execute('INSERT OR IGNORE INTO users (username, password_hash, salt) VALUES (?, ?, ?)',
               ('suchao', hash_password("19880130", default_salt), default_salt))
    columns = [col[1] for col in db.fetchall("PRAGMA table_info(predictions)")]
    if 'group_id' not in columns:
        db.execute("ALTER TABLE predictions ADD COLUMN group_id TEXT")
    if 'predict_mode' not in columns:
        db.execute("ALTER TABLE predictions ADD COLUMN predict_mode TEXT DEFAULT 'normal'")
    if 'extra_info' not in columns:
        db.execute("ALTER TABLE predictions ADD COLUMN extra_info TEXT DEFAULT ''")

def insert_record(table, period, date, front, back):
    db = get_db()
    db.execute(f'INSERT OR REPLACE INTO {table} VALUES (?,?,?,?,?,?,?,?,?)',
               (period, date, front[0], front[1], front[2], front[3], front[4], back[0], back[1]))

def fetch_records(table, limit=None):
    db = get_db()
    rows = db.fetchall(f'SELECT * FROM {table} ORDER BY date DESC' + (f' LIMIT {limit}' if limit else ''))
    return [{"period": r[0], "date": r[1], "front": [r[2],r[3],r[4],r[5],r[6]], "back": [r[7],r[8]]} for r in rows]

def clear_table(table):
    get_db().execute(f'DELETE FROM {table}')

def get_merged_records():
    recs = fetch_records('excel_history') + fetch_records('online_latest')
    unique = {}
    for r in recs:
        if r['period'] not in unique or r['date'] > unique[r['period']]['date']:
            unique[r['period']] = r
    merged = list(unique.values())
    merged.sort(key=lambda x: x['date'], reverse=True)
    return merged

def get_all_periods():
    records = get_merged_records()
    periods = []
    for r in records:
        if r['period'] not in periods:
            periods.append(r['period'])
    return periods

def get_draw_by_period(period):
    db = get_db()
    row = db.fetchone('SELECT front1,front2,front3,front4,front5,back1,back2 FROM excel_history WHERE period=?', (period,))
    if not row:
        row = db.fetchone('SELECT front1,front2,front3,front4,front5,back1,back2 FROM online_latest WHERE period=?', (period,))
    if row:
        return {"front": [row[0],row[1],row[2],row[3],row[4]], "back": [row[5],row[6]]}
    return None

def get_record_count(table):
    row = get_db().fetchone(f'SELECT COUNT(*) FROM {table}')
    return row[0] if row else 0

def save_predictions(tickets, mode='normal', extra_info=None):
    db = get_db()
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    extra_str = json.dumps(extra_info, ensure_ascii=False) if extra_info else ''
    for front, back in tickets:
        db.execute('INSERT INTO predictions (group_id, timestamp, predicted_front, predicted_back, predict_mode, extra_info) VALUES (?, ?, ?, ?, ?, ?)',
                   (ts, ts, ' '.join(map(str, front)), ' '.join(map(str, back)), mode, extra_str))

def update_feedback(pred_id, actual_front, actual_back):
    db = get_db()
    row = db.fetchone('SELECT predicted_front, predicted_back FROM predictions WHERE id=?', (pred_id,))
    if not row: return 0, 0
    pred_f = list(map(int, row[0].split()))
    pred_b = list(map(int, row[1].split()))
    hit_front = min(len(set(pred_f) & set(actual_front)), 5)
    hit_back = min(len(set(pred_b) & set(actual_back)), 2)
    db.execute('UPDATE predictions SET actual_front=?, actual_back=?, is_feedback=1, hit_front=?, hit_back=? WHERE id=?',
               (' '.join(map(str, actual_front)), ' '.join(map(str, actual_back)), hit_front, hit_back, pred_id))
    return hit_front, hit_back

def get_prediction_groups(feedback_status=None):
    db = get_db()
    if feedback_status is not None:
        return db.fetchall('SELECT DISTINCT group_id, timestamp FROM predictions WHERE is_feedback=? ORDER BY timestamp DESC', (feedback_status,))
    return db.fetchall('SELECT DISTINCT group_id, timestamp FROM predictions ORDER BY timestamp DESC')

def get_group_predictions(group_id):
    return get_db().fetchall(
        'SELECT id, predicted_front, predicted_back, predict_mode, extra_info FROM predictions WHERE group_id=?',
        (group_id,))

def get_prize_info(hit_front, hit_back):
    key = (hit_front, hit_back)
    if key in PRIZE_RULES:
        return PRIZE_RULES[key]
    return ("未中奖", 0, "")

# ============================================================
# 智能组号
# ============================================================
def smart_regroup(tickets, validator=None, target_count=None, rounds=1200):
    """
    智能重组：以原有号码频次为权重重新组号。
    关键：重组结果必须通过 validator（前区规则校验），
          不再产出和值/奇偶/跨度失控的注数。
    """
    if len(tickets) < 2: return tickets
    front_counter = Counter(); back_counter = Counter()
    for f, b in tickets:
        front_counter.update(f); back_counter.update(b)
    front_sorted = [n for n, _ in sorted(front_counter.items(), key=lambda kv: (-kv[1], kv[0]))]
    back_sorted = [n for n, _ in sorted(back_counter.items(), key=lambda kv: (-kv[1], kv[0]))]
    n = target_count or len(tickets)

    # 权重池：频次越高被抽中概率越大，但仍保留低权重号码的可能
    front_weights = [front_counter.get(x, 0) + 1 for x in front_sorted]
    back_weights = [back_counter.get(x, 0) + 1 for x in back_sorted]

    def pick_front():
        """按权重不放回抽样，保证 5 个互不相同的号。"""
        if len(front_sorted) < 5: return None
        pool = list(front_sorted); w = list(front_weights); picked = []
        for _ in range(5):
            i = random.choices(range(len(pool)), weights=w, k=1)[0]
            picked.append(pool.pop(i)); w.pop(i)
        return sorted(picked)

    def pick_back():
        if len(back_sorted) < 2: return None
        pool = list(back_sorted); w = list(back_weights); picked = []
        for _ in range(2):
            i = random.choices(range(len(pool)), weights=w, k=1)[0]
            picked.append(pool.pop(i)); w.pop(i)
        return sorted(picked)

    out = []; seen = set()
    # 第一轮：严格按 validator 校验
    for _ in range(rounds):
        if len(out) >= n: break
        f = pick_front(); b = pick_back()
        if not f or not b: break
        f = sorted(set(f))
        if len(f) != 5: continue
        if validator and not validator(f):
            continue
        b = sorted(set(b))
        if len(b) != 2: continue
        key = (tuple(f), tuple(b))
        if key in seen: continue
        seen.add(key); out.append((f, b))
    # 第二轮：候选不足时放宽 validator
    if len(out) < n and validator:
        for _ in range(rounds):
            if len(out) >= n: break
            f = pick_front(); b = pick_back()
            if not f or not b: break
            f = sorted(set(f))
            if len(f) != 5: continue
            if not validator(f, relax=2): continue
            b = sorted(set(b))
            if len(b) != 2: continue
            key = (tuple(f), tuple(b))
            if key in seen: continue
            seen.add(key); out.append((f, b))
    return out if out else tickets

# ============================================================
# 右键菜单
# ============================================================
def add_right_click_menu(widget):
    menu = tk.Menu(widget, tearoff=0)
    menu.add_command(label="剪切", command=lambda: widget.event_generate("<<Cut>>"))
    menu.add_command(label="复制", command=lambda: widget.event_generate("<<Copy>>"))
    menu.add_command(label="粘贴", command=lambda: widget.event_generate("<<Paste>>"))
    menu.add_command(label="全选", command=lambda: _select_all(widget))
    widget.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))
    widget.bind("<Button-2>", lambda e: menu.tk_popup(e.x_root, e.y_root))

def _select_all(widget):
    try:
        widget.tag_add("sel", "1.0", "end"); widget.mark_set("insert", "1.0")
    except:
        try:
            widget.select_range(0, tk.END); widget.icursor(tk.END)
        except: pass

# ============================================================
# 工具函数
# ============================================================
def parse_numbers(text, max_num=35, count=None):
    if not text or not text.strip(): return []
    parts = re.split(r'[\s,，、;；]+', text.strip())
    nums = [int(p) for p in parts if p.isdigit() and 1 <= int(p) <= max_num]
    if count and len(nums) != count: return []
    return nums

def format_numbers(nums): return " ".join(f"{n:02d}" for n in nums)

def parse_ratio(text, expected_sum=5):
    if not text or not text.strip(): return None
    try:
        nums = [int(p) for p in text.strip().split(':')]
        return tuple(nums) if sum(nums) == expected_sum else None
    except: return None

def safe_int(s, default=0):
    try: return int(str(s).strip())
    except Exception: return default

def build_pair_down_pool(records):
    """对号下号法：遍历所有记录的前区号码，按 PAIR_MAP 映射出下号，汇总去重排序返回。"""
    pool = set()
    for r in records:
        for n in r.get('front', []):
            if n in PAIR_MAP:
                for p in PAIR_MAP[n]:
                    pool.add(p)
    return sorted(pool)

# ============================================================
# 走势分析
# ============================================================
class TrendAnalyzer:
    def __init__(self, records):
        self.records = sorted(records, key=lambda x: x['date'], reverse=True)
    def get_repeat_scores(self):
        scores = {num: 0 for num in range(1, 36)}
        if len(self.records) < 2: return scores
        if not self.records[0].get('front') or not self.records[1].get('front'): return scores
        latest = set(self.records[0]['front']); prev = set(self.records[1]['front'])
        for num in latest & prev: scores[num] += 2
        if len(self.records) >= 3:
            third = set(self.records[2]['front'])
            for num in latest & third: scores[num] += 1
        return scores
    def get_oblique_scores(self):
        scores = {num: 0 for num in range(1, 36)}
        if not self.records: return scores
        prev = set(self.records[0]['front'])
        for num in range(1, 36):
            if num - 1 in prev or num + 1 in prev: scores[num] += 1
        return scores
    def get_fill_scores(self):
        scores = {num: 0 for num in range(1, 36)}
        if not self.records: return scores
        prev = sorted(self.records[0]['front'])
        for i in range(len(prev) - 1):
            for num in range(prev[i]+1, prev[i+1]):
                if 1 <= num <= 35: scores[num] += 1
        return scores
    def get_same_tail_scores(self):
        scores = {num: 0 for num in range(1, 36)}
        tail_counts = Counter()
        for rec in self.records[:5]:
            for num in rec['front']: tail_counts[num % 10] += 1
        for num in range(1, 36):
            if tail_counts[num % 10] >= 2: scores[num] += 1
        return scores
    def get_hot_scores(self):
        scores = {num: 0 for num in range(1, 36)}
        if not self.records: return scores
        total = min(10, len(self.records))
        counter = Counter()
        for rec in self.records[:total]:
            for num in (rec.get('front') or []): counter[num] += 1
        for num, cnt in counter.items():
            if cnt >= total * 0.7: scores[num] += 2
        return scores
    def get_combined_scores(self):
        combined = {num: 0 for num in range(1, 36)}
        for func in [self.get_repeat_scores, self.get_oblique_scores, self.get_fill_scores,
                     self.get_same_tail_scores, self.get_hot_scores]:
            for num, sc in func().items(): combined[num] += sc
        return combined

# ============================================================
# 圆角按钮
# ============================================================
class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command, width=90, height=32, bg="#6C9BCF", fg="white",
                 font=("微软雅黑",9), parent_bg="#E8E0D5", **kw):
        super().__init__(parent, width=width, height=height, bg=parent_bg, highlightthickness=0, **kw)
        self.command=command; self.bg=bg; self.fg=fg; self.font=font; self.width=width; self.height=height
        self.radius=12; self.text=text
        self.draw_button()
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self.on_enter); self.bind("<Leave>", self.on_leave)
    def _on_click(self, e):
        try:
            st = str(self.cget("state"))
        except Exception:
            st = "normal"
        if st == "disabled": return
        self.command()
    def draw_button(self, color=None):
        self.delete("all")
        c = color or self.bg
        self.create_rounded_rect(2,2,self.width-2,self.height-2,self.radius,fill=c,outline="")
        self.create_text(self.width/2, self.height/2, text=self.text, fill=self.fg, font=self.font)
    def create_rounded_rect(self, x1,y1,x2,y2,r,**kw):
        points = [x1+r,y1,x2-r,y1,x2,y1,x2,y1+r,x2,y2-r,x2,y2,x2-r,y2,x1+r,y2,x1,y2,x1,y2-r,x1,y1+r,x1,y1]
        return self.create_polygon(points, smooth=True, **kw)
    def on_enter(self, e):
        try:
            r,g,b = self.winfo_rgb(self.bg); r,g,b = r//256,g//256,b//256
            r,g,b = min(255,r+20), min(255,g+20), min(255,b+20)
            self.draw_button(f'#{r:02x}{g:02x}{b:02x}')
        except Exception:
            pass
    def on_leave(self, e): self.draw_button()

# ============================================================
# AI 预测器
# ============================================================
class AIPredictor:
    FEATURES_PER_NUM = 16

    def __init__(self, records, log_func=None):
        self.records = records; self.models = {}; self.scaler = StandardScaler(); self.log_func = log_func
    def __getstate__(self):
        state = self.__dict__.copy(); state['log_func'] = None; return state
    def __setstate__(self, state):
        self.__dict__.update(state); self.log_func = None
    def _extract_features(self, idx):
        past = self.records[idx:] if idx > 0 else self.records
        if not past: return [0] * (self.FEATURES_PER_NUM * 35)
        latest_front = past[0]['front']; feats = []
        for num in range(1,36):
            om = 0
            for rec in past:
                if num in rec['front']: break
                om += 1
            feats.append(om)
            tier = 0 if om<=2 else (1 if om<=7 else (2 if om<=14 else 3))
            feats.append(tier)
            feats.append(sum(1 for rec in past[:5] if num in rec['front']))
            feats.append(sum(1 for rec in past[:10] if num in rec['front']))
            feats.append(sum(1 for rec in past[:20] if num in rec['front']))
            max_om=0; cur=0
            for rec in past:
                if num in rec['front']: max_om=max(max_om,cur); cur=0
                else: cur+=1
            feats.append(max(max_om,cur))
            om_seq=[]; cur=0
            for rec in past:
                if num in rec['front']: om_seq.append(cur); cur=0
                else: cur+=1
            feats.append(np.mean(om_seq) if om_seq else om)
            zid = 0 if num<=12 else (1 if num<=24 else 2)
            for j in range(3): feats.append(1 if j==zid else 0)
            feats.append(1 if num%2==1 else 0)
            feats.append(1 if num in PRIMES else 0)
            feats.append(num%10)
            feats.append(1 if num in latest_front else 0)
            neighbor = set()
            for n in latest_front:
                if n-1>=1: neighbor.add(n-1)
                if n+1<=35: neighbor.add(n+1)
            feats.append(1 if num in neighbor else 0)
            adj_cnt=0
            if num-1>=1: adj_cnt += sum(1 for rec in past[:5] if num-1 in rec['front'])
            if num+1<=35: adj_cnt += sum(1 for rec in past[:5] if num+1 in rec['front'])
            feats.append(adj_cnt)
        return feats
    def build_features(self):
        X = []; Y = {num:[] for num in range(1,36)}
        n = len(self.records)
        for i in range(n - 1):
            X.append(self._extract_features(i + 1))
            front_set = set(self.records[i]['front'])
            for num in range(1,36):
                Y[num].append(1 if num in front_set else 0)
        return np.array(X), Y
    def train(self):
        X, Y = self.build_features()
        if len(X) < 10: return False
        X_scaled = self.scaler.fit_transform(X)
        for num in range(1,36):
            clf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42, n_jobs=-1)
            clf.fit(X_scaled, Y[num]); self.models[num] = clf
        return True
    def predict_proba(self, latest_features):
        probs = {}
        latest = np.array([latest_features]); latest_scaled = self.scaler.transform(latest)
        for num in range(1, 36):
            if num in self.models:
                try: prob = self.models[num].predict_proba(latest_scaled)[0, 1]
                except IndexError:
                    classes = self.models[num].classes_
                    prob = 1.0 if (len(classes)==1 and classes[0]==1) else 0.0
            else: prob = 0.0
            probs[num] = prob
        return probs
    def generate_ai_front(self, candidate_pool=None, num_select=5, manual_front=None,
                          broken_zones=None, kill_front=None, validator=None):
        """
        按 AI 概率加权选号。
        validator: 可选的前区校验函数（如 NumberGenerator._validate_front）。
                   传入时最多重试若干次以产出合规号码，避免 AI 输出违反和值/奇偶/跨度规则。
        """
        if manual_front and len(manual_front) >= num_select:
            return sorted(list(set(manual_front))[:num_select])
        latest_feats = self._extract_features(0)
        probs = self.predict_proba(latest_feats)
        locked = set(manual_front or []); disabled = set(kill_front or [])
        if broken_zones:
            for z in broken_zones: disabled.update(ZONES[z-1])
        pool = set(candidate_pool) if candidate_pool else set(range(1, 36))
        allowed = [n for n in pool if n not in disabled or n in locked]

        def _one_shot():
            if len(allowed) < num_select - len(locked):
                remaining = [n for n in pool if n not in locked]
                if len(remaining) < num_select - len(locked):
                    return sorted(locked | set(remaining))
                return sorted(random.sample(remaining, num_select - len(locked)) | locked)
            need = num_select - len(locked)
            allowed_no_lock = [n for n in allowed if n not in locked]
            if len(allowed_no_lock) < need:
                return sorted(set(random.sample([n for n in pool if n not in locked], need)) | locked)
            proba = np.array([probs.get(n, 0.0) for n in allowed_no_lock], dtype=float)
            proba = np.clip(proba, 0, None)
            tot = proba.sum()
            proba = np.ones(len(allowed_no_lock))/len(allowed_no_lock) if tot == 0 else proba/tot
            try:
                sel = list(np.random.choice(allowed_no_lock, size=need, replace=False, p=proba))
            except ValueError:
                sel = list(np.random.choice(allowed_no_lock, size=need, replace=False))
            return sorted(locked.union(set(sel)))

        if not validator:
            return _one_shot()
        # 严格校验优先，逐级放宽兜底
        for relax in (0, 1, 2, 3):
            for _ in range(300 if relax == 0 else 150):
                cand = _one_shot()
                if len(cand) == num_select and validator(cand, relax=relax):
                    return cand
        return _one_shot()

# ============================================================
# 遗漏分析
# ============================================================
class OmissionAnalyzer:
    def __init__(self, records):
        self.records = sorted(records, key=lambda x: x.get("date", ""), reverse=True)
        self.front_omission = {}; self.back_omission = {}; self.tier_map = {}
        self.calculate_omissions(); self.assign_tiers()
    def calculate_omissions(self):
        if not self.records: return
        for num in FRONT_RANGE:
            om = 0
            for r in self.records:
                if num in r.get("front", []): break
                om += 1
            self.front_omission[num] = om
        for num in BACK_RANGE:
            om = 0
            for r in self.records:
                if num in r.get("back", []): break
                om += 1
            self.back_omission[num] = om
    def assign_tiers(self):
        self.tier_map = {}
        for num, om in self.front_omission.items():
            if om <= 2: self.tier_map[num] = "热"
            elif om <= 7: self.tier_map[num] = "温"
            elif om <= 14: self.tier_map[num] = "冷"
            else: self.tier_map[num] = "极冷"
    def get_tier_numbers(self):
        return ([n for n,t in self.tier_map.items() if t=="热"],
                [n for n,t in self.tier_map.items() if t=="温"],
                [n for n,t in self.tier_map.items() if t=="冷"],
                [n for n,t in self.tier_map.items() if t=="极冷"])
    def get_recommended_odd_even(self, periods=30):
        return core.recommend_odd_even(self.records, periods)
    def get_recommended_zone_ratio(self, periods=30, broken_zones=None):
        if broken_zones is None: broken_zones = []
        return core.recommend_zone_ratio(self.records, periods, broken_zones=broken_zones)

# ============================================================
# 号码生成器
# ============================================================
class NumberGenerator:
    def __init__(self, records, mode='normal', **kwargs):
        self.records = records; self.analyzer = OmissionAnalyzer(records)
        self.trend = TrendAnalyzer(records) if records else None
        self.mode = mode
        self.broken_zones = kwargs.get('broken_zones', [])
        self.odd_even_ratio = kwargs.get('odd_even_ratio')
        self.zone_ratio = kwargs.get('zone_ratio')
        self.use_ai = kwargs.get('use_ai', False)
        self.log_func = kwargs.get('log_func')
        self.kill_front = kwargs.get('kill_front', [])
        self.kill_back = kwargs.get('kill_back', [])
        self.ai_predictor = AIPredictor(records, log_func=self.log_func) if self.use_ai else None
        self.dantuo_front_dan = [n for n in kwargs.get('dantuo_front_dan', []) if n not in self.kill_front]
        self.dantuo_front_tuo = kwargs.get('dantuo_front_tuo', [])
        self.dantuo_back_dan = [n for n in kwargs.get('dantuo_back_dan', []) if n not in self.kill_back]
        self.dantuo_back_tuo = kwargs.get('dantuo_back_tuo', [])
        self.fushi_front_count = kwargs.get('fushi_front_count', 5)
        self.fushi_back_count = kwargs.get('fushi_back_count', 2)
        self.manual_front = list(dict.fromkeys([n for n in kwargs.get('manual_front', []) if n not in self.kill_front]))
        self.manual_back = list(dict.fromkeys([n for n in kwargs.get('manual_back', []) if n not in self.kill_back]))
        fp = kwargs.get('front_pool')
        self.front_pool = list(fp) if fp is not None else list(range(1, 36))
        self.strict_pool = kwargs.get('strict_pool', False)
        ffp = kwargs.get('fushi_front_pool')
        fbp = kwargs.get('fushi_back_pool')
        self.fushi_front_pool = list(ffp) if ffp is not None else None
        self.fushi_back_pool = list(fbp) if fbp is not None else None
        # 遗漏分层权重（热/温/冷/极冷）。默认让"热号优先、极冷回补"，
        # 使分层真正参与选号，而不是只用于界面显示。
        self.tier_weights = kwargs.get('tier_weights') or {
            'hot': 2.4, 'warm': 1.6, 'cold': 1.1, 'frozen': 1.5
        }

    def _get_tier_weights_map(self):
        """返回 {号码: 分层权重}。无历史数据时全部为 1.0。"""
        w = {n: 1.0 for n in range(1, 36)}
        try:
            tiers = self.analyzer.get_tier_numbers()
        except Exception:
            return w
        if not tiers:
            return w
        # get_tier_numbers 返回四元组：(热, 温, 冷, 极冷)
        names = ('hot', 'warm', 'cold', 'frozen')
        for name, nums in zip(names, tiers):
            weight = self.tier_weights.get(name, 1.0)
            for n in nums:
                if n in w:
                    w[n] = weight
        return w

    def _get_trend_scores(self):
        return self.trend.get_combined_scores() if self.trend else {num: 0 for num in range(1, 36)}

    def _validate_front(self, selected, relax=0):
        """
        校验一注前区。relax 逐级放宽，用于候选池不足时的降级：
          relax=0 全部规则；relax=1 放宽度/连号/对码；relax=2 仅和值+奇偶+跨度；relax=3 仅和值+奇偶
        """
        if len(selected) != 5: return False
        total = sum(selected)
        if not (80 <= total <= 105): return False
        odd = sum(1 for n in selected if n % 2)
        if self.odd_even_ratio:
            if odd != self.odd_even_ratio[0]: return False
        else:
            if odd not in (2, 3): return False
        if relax >= 3: return True
        span = max(selected) - min(selected)
        if not (20 <= span <= 30): return False
        if relax >= 2: return True
        # 区间比（原 zone_ratio 只赋值未使用，此处真正生效）
        if self.zone_ratio:
            zc = [0, 0, 0]
            for n in selected:
                zc[0 if n <= 12 else (1 if n <= 24 else 2)] += 1
            if tuple(zc) != tuple(self.zone_ratio): return False
        manual_set = set(self.manual_front or [])
        check_nums = [n for n in selected if n not in manual_set]
        for zone_idx in self.broken_zones:
            if any(n in ZONES[zone_idx-1] for n in check_nums): return False
        if relax >= 1: return True
        sorted_sel = sorted(selected)
        for i in range(len(sorted_sel) - 2):
            if sorted_sel[i+2] - sorted_sel[i] == 2: return False
        for n in selected:
            if n in PAIR_MAP:
                for p in PAIR_MAP[n]:
                    if n == 33 and p == 33: continue
                    if p in selected and p != n: return False
        return True

    def _select_front_from_pool(self, pool, num_select=5, locked=None, strict_pool=False):
        locked = locked or []; pool = list(set(pool))
        disabled = set(self.kill_front)
        if self.broken_zones:
            for zone_idx in self.broken_zones: disabled.update(ZONES[zone_idx-1])
        pool = [n for n in pool if n not in disabled]
        need = num_select if len(locked) >= num_select else num_select - len(locked)
        supplement_pool = [n for n in pool if n not in locked and n not in disabled]
        if len(supplement_pool) < need:
            if strict_pool:
                raise ValueError(
                    f"号码池经杀号/断区过滤后不足 {num_select} 个（需 {need} 个，"
                    f"当前仅 {len(supplement_pool)} 个），请调整杀号或断区")
            supplement_pool = [n for n in range(1, 36) if n not in locked and n not in disabled]
        trend_scores = self._get_trend_scores()
        # 采样权重 = 遗漏分层权重 × 趋势分 × AI 概率
        tier_w = self._get_tier_weights_map()
        ai_weights = None
        if self.use_ai and self.ai_predictor and getattr(self.ai_predictor, 'models', None):
            try:
                probs = self.ai_predictor.predict_proba(self.ai_predictor._extract_features(0))
                ai_weights = {n: float(probs.get(n, 0.0)) for n in supplement_pool}
            except Exception:
                ai_weights = None

        def _weighted_pick():
            pl = list(supplement_pool)
            wl = []
            for n in pl:
                w = tier_w.get(n, 1.0)
                w *= (1.0 + max(0.0, trend_scores.get(n, 0)))   # 趋势分加成
                if ai_weights is not None:
                    w *= (ai_weights.get(n, 0.0) + 1e-3)          # AI 概率加成
                wl.append(max(w, 1e-9))
            picked = []
            for _ in range(need):
                i = random.choices(range(len(pl)), weights=wl, k=1)[0]
                picked.append(pl.pop(i)); wl.pop(i)
            return sorted(locked + picked)

        for _ in range(800):
            if len(supplement_pool) < need: break
            selected = _weighted_pick()
            if self._validate_front(selected): return selected
        sorted_pool = sorted(supplement_pool, key=lambda x: trend_scores.get(x, 0), reverse=True)
        for i in range(len(sorted_pool) - need + 1):
            selected = sorted(locked + sorted_pool[i:i+need])
            if self._validate_front(selected): return selected
        # 兜底：逐级放宽。仍无解时【明确报错】，绝不静默输出违规号码。
        for relax in range(1, 4):
            for _ in range(600):
                if len(supplement_pool) < need: break
                selected = sorted(locked + random.sample(supplement_pool, need))
                if self._validate_front(selected, relax=relax): return selected
        raise ValueError(
            f"当前号码池（{len(supplement_pool)} 个可用号）无法满足选号规则："
            f"和值 80-105、奇数 2-3、跨度 20-30 无解。"
            f"请减少断区/杀号，或放宽规则后重试")

    def _select_back_from_pool(self, pool, num_select=2, locked=None):
        locked = locked or []; pool = list(set(pool))
        if self.kill_back: pool = [n for n in pool if n not in self.kill_back]
        need = num_select if len(locked) >= num_select else num_select - len(locked)
        for _ in range(300):
            if len(pool) < need: break
            back = sorted(locked + random.sample(pool, need))
            if sum(1 for n in back if n%2) == 1 and 8 <= sum(back) <= 18 and back[0]%10 != back[1]%10:
                return back
        for _ in range(300):
            if len(pool) < need: break
            back = sorted(locked + random.sample(pool, need))
            if sum(1 for n in back if n%2) == 1: return back
        if len(pool) >= need: return sorted(locked + random.sample(pool, need))
        return sorted(locked + pool)

    def generate(self):
        if self.mode == 'normal':
            if len(self.manual_front) >= 5:
                front = sorted(set(self.manual_front))[:5]
            else:
                front = self._select_front_from_pool(
                    self.front_pool, 5, locked=self.manual_front,
                    strict_pool=self.strict_pool)
            back = self._select_back_from_pool(self.manual_back, 2) if len(self.manual_back)>=2 else self._select_back_from_pool(range(1,13), 2, locked=self.manual_back)
            return ('normal', front, back)
        elif self.mode == 'dantuo':
            disabled = set(self.kill_front)
            if self.broken_zones:
                for zi in self.broken_zones: disabled.update(ZONES[zi-1])
            dan_f = list(set(self.dantuo_front_dan)); tuo_f = list(set(self.dantuo_front_tuo))
            if len(dan_f) >= 5: front = sorted(dan_f[:5])
            else:
                need = 5 - len(dan_f)
                tuo_clean = [n for n in tuo_f if n not in dan_f and n not in disabled]
                if len(tuo_clean) < need: raise ValueError(f"红拖码不足，需要至少 {need} 个，当前只有 {len(tuo_clean)} 个")
                front = sorted(dan_f + random.sample(tuo_clean, need))
            dan_b = list(set(self.dantuo_back_dan)); tuo_b = list(set(self.dantuo_back_tuo))
            if len(dan_b) >= 2: back = sorted(dan_b[:2])
            else:
                need = 2 - len(dan_b)
                tuo_clean = [n for n in tuo_b if n not in dan_b and n not in self.kill_back]
                if len(tuo_clean) < need: raise ValueError(f"蓝拖码不足，需要至少 {need} 个，当前只有 {len(tuo_clean)} 个")
                back = sorted(dan_b + random.sample(tuo_clean, need))
            return ('dantuo', front, back)
        elif self.mode == 'fushi':
            fc = min(max(self.fushi_front_count, 5), 18)
            bc = min(max(self.fushi_back_count, 2), 12)
            fbase = self.fushi_front_pool if self.fushi_front_pool is not None else list(range(1, 36))
            disabled_f = set(self.kill_front)
            if self.broken_zones:
                for zi in self.broken_zones: disabled_f.update(ZONES[zi-1])
            avail_f = [n for n in fbase if n not in disabled_f]
            if len(avail_f) < 5:
                raise ValueError(
                    f"复式前区号码池（去杀号/断区后）不足 5 个（当前 {len(avail_f)} 个），"
                    f"请先做一次普通预测或调整杀号/断区")
            if fc > len(avail_f): fc = len(avail_f)
            front = sorted(random.sample(avail_f, fc))
            bbase = self.fushi_back_pool if self.fushi_back_pool is not None else list(range(1, 13))
            avail_b = [n for n in bbase if n not in self.kill_back]
            if len(avail_b) < 2:
                raise ValueError(
                    f"复式后区号码池（去杀号后）不足 2 个（当前 {len(avail_b)} 个）")
            if bc > len(avail_b): bc = len(avail_b)
            back = sorted(random.sample(avail_b, bc))
            return ('fushi', front, back)

# ============================================================
# 登录窗口
# ============================================================
class LoginWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master, bg=COLORS["bg_main"])
        self.master = master
        self.title("登录")
        self.geometry("320x240")
        self.resizable(False, False)
        self.center_window()
        try: self.iconbitmap(resource_path("app.ico"))
        except: pass
        tk.Label(self, text=f"大乐透预测软件 {VERSION}", font=("微软雅黑",14,"bold"), bg=COLORS["bg_main"]).pack(pady=10)
        tk.Label(self, text="用户名:", bg=COLORS["bg_main"]).pack()
        self.user_entry = tk.Entry(self, font=("微软雅黑",10)); self.user_entry.pack(pady=2)
        add_right_click_menu(self.user_entry)
        tk.Label(self, text="密码:", bg=COLORS["bg_main"]).pack()
        self.pw_entry = tk.Entry(self, show="*", font=("微软雅黑",10)); self.pw_entry.pack(pady=2)
        add_right_click_menu(self.pw_entry)
        self.user_entry.bind("<Return>", lambda e: self.do_login())
        self.pw_entry.bind("<Return>", lambda e: self.do_login())
        btn_frame = tk.Frame(self, bg=COLORS["bg_main"]); btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="登录", command=self.do_login, bg=COLORS["accent_blue"], fg="white", font=("微软雅黑",10), padx=15).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="修改密码", command=self.change_password, bg=COLORS["accent_green"], fg="white", font=("微软雅黑",10)).pack(side=tk.LEFT, padx=5)
        self.protocol("WM_DELETE_WINDOW", self.master.destroy)
    def center_window(self):
        w, h = 320, 240
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f'{w}x{h}+{x}+{y}')
    def verify(self, user, pw):
        row = get_db().fetchone('SELECT password_hash, salt FROM users WHERE username=?', (user,))
        if not row:
            return False
        stored, salt = row[0], row[1] or ''
        return stored == hash_password(pw, salt)
    def do_login(self):
        if self.verify(self.user_entry.get().strip(), self.pw_entry.get().strip()):
            self.master.deiconify(); self.destroy()
        else: messagebox.showerror("错误", "用户名或密码错误")
    def change_password(self):
        dlg = tk.Toplevel(self, bg=COLORS["bg_main"]); dlg.title("修改密码"); dlg.geometry("280x220")
        try: dlg.iconbitmap(resource_path("app.ico"))
        except: pass
        tk.Label(dlg, text="原密码:", bg=COLORS["bg_main"]).pack(pady=2)
        old = tk.Entry(dlg, show="*"); old.pack(); add_right_click_menu(old)
        tk.Label(dlg, text="新密码:", bg=COLORS["bg_main"]).pack(pady=2)
        new = tk.Entry(dlg, show="*"); new.pack(); add_right_click_menu(new)
        tk.Label(dlg, text="确认新密码:", bg=COLORS["bg_main"]).pack(pady=2)
        confirm = tk.Entry(dlg, show="*"); confirm.pack(); add_right_click_menu(confirm)
        def submit():
            if new.get() != confirm.get(): messagebox.showwarning("警告","两次输入不一致"); return
            user = self.user_entry.get().strip()
            if not self.verify(user, old.get()): messagebox.showerror("错误","原密码错误"); return
            salt = os.urandom(16).hex()
            get_db().execute('UPDATE users SET password_hash=?, salt=? WHERE username=?',
                             (hash_password(new.get(), salt), salt, user))
            messagebox.showinfo("成功", "密码已修改"); dlg.destroy()
        tk.Button(dlg, text="确认修改", command=submit, bg=COLORS["accent_green"], fg="white").pack(pady=10)

# ============================================================
# 主应用
# ============================================================
class LottoApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"大乐透预测软件 {VERSION}")
        self.root.geometry("1200x800"); self.root.minsize(1000, 700)
        self.root.configure(bg=COLORS["bg_main"]); self.root.withdraw()
        init_db()
        self.servers = load_servers()
        self.ai_cfg = self._load_ai_config()
        self.current_records = []
        self.data_source = tk.StringVar(value="excel")
        self.ai_predictor = None
        self.predict_btn = None
        self.last_tickets = []
        self.original_tickets = []
        self.front_pool_mode = tk.StringVar(value="down")
        self.build_ui()
        try: self.root.iconbitmap(resource_path("app.ico"))
        except: pass
        self.log(f"✨ 大乐透预测软件 {VERSION} 已启动，请登录。")
        LoginWindow(self.root)

    # ------------------------------------------------------------
    # AI 配置（免费大模型接入）
    # ------------------------------------------------------------
    def _load_ai_config(self):
        try:
            if os.path.exists('ai_config.json'):
                with open('ai_config.json', 'r', encoding='utf-8') as f:
                    return lai.AIConfig.from_dict(json.load(f))
        except Exception as e:
            self.log(f"AI配置读取失败：{e}")
        return lai.AIConfig()

    def _save_ai_config(self):
        try:
            with open('ai_config.json', 'w', encoding='utf-8') as f:
                json.dump(self.ai_cfg.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log(f"AI配置保存失败：{e}")

    def ai_settings(self):
        """AI/模型设置窗口：选免费模型、填 Key、开关。"""
        cfg = self.ai_cfg
        dlg = tk.Toplevel(self.root, bg=COLORS["bg_main"])
        dlg.title("AI/模型设置"); dlg.geometry("480x420")
        try: dlg.iconbitmap(resource_path("app.ico"))
        except: pass
        frame = tk.Frame(dlg, bg=COLORS["bg_main"]); frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        enable_var = tk.BooleanVar(value=cfg.enabled)
        tk.Checkbutton(frame, text="启用免费AI大模型辅助选号", variable=enable_var,
                       bg=COLORS["bg_main"], font=("微软雅黑", 10, "bold")).pack(anchor="w")

        tk.Label(frame, text="服务商(免费/低价模型):", bg=COLORS["bg_main"]).pack(anchor="w", pady=(10, 2))
        provider_var = tk.StringVar(value=cfg.provider)
        prov = ttk.Combobox(frame, textvariable=provider_var,
                            values=list(lai.PROVIDER_PRESETS.keys()), state="readonly")
        prov.pack(fill=tk.X)

        tk.Label(frame, text="API Key:", bg=COLORS["bg_main"]).pack(anchor="w", pady=(8, 2))
        key_entry = tk.Entry(frame, width=50, show="•")
        key_entry.insert(0, cfg.api_key); key_entry.pack(fill=tk.X)

        tk.Label(frame, text="Base URL(可从预设自动填充):", bg=COLORS["bg_main"]).pack(anchor="w", pady=(8, 2))
        url_var = tk.StringVar(value=cfg.base_url)
        tk.Entry(frame, textvariable=url_var, width=50).pack(fill=tk.X)

        tk.Label(frame, text="模型名:", bg=COLORS["bg_main"]).pack(anchor="w", pady=(8, 2))
        model_var = tk.StringVar(value=cfg.model)
        tk.Entry(frame, textvariable=model_var, width=50).pack(fill=tk.X)

        def on_provider(evt=None):
            p = provider_var.get()
            if p in lai.PROVIDER_PRESETS:
                url_var.set(lai.PROVIDER_PRESETS[p]["base_url"])
                model_var.set(lai.PROVIDER_PRESETS[p]["model"])
        prov.bind("<<ComboboxSelected>>", on_provider)

        def save():
            cfg.enabled = enable_var.get()
            cfg.provider = provider_var.get()
            cfg.api_key = key_entry.get().strip()
            cfg.base_url = url_var.get().strip()
            cfg.model = model_var.get().strip()
            self._save_ai_config()
            self.log(f"🤖 AI设置已保存：{'开' if cfg.enabled else '关'} / {cfg.provider} / {cfg.model}")
            messagebox.showinfo("成功", "AI设置已保存")
            dlg.destroy()
        tk.Button(frame, text="保存", command=save, bg=COLORS["accent_green"], fg="white",
                  font=("微软雅黑", 10), padx=20).pack(pady=12)
        self.center_dialog(dlg)

    def center_dialog(self, dlg):
        dlg.update_idletasks()
        w, h = dlg.winfo_width(), dlg.winfo_height()
        x = (dlg.winfo_screenwidth() // 2) - (w // 2)
        y = (dlg.winfo_screenheight() // 2) - (h // 2)
        dlg.geometry(f'+{x}+{y}')

    def log(self, msg):
        self.log_text.insert(tk.END, f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.log_text.see(tk.END)

    def _update_bet_log_line(self, msg):
        """日志区注数行：删除上一次后插入新行，不累积。"""
        # 循环删除所有带 bet_info tag 的内容
        while True:
            rngs = self.log_text.tag_ranges("bet_info")
            if len(rngs) < 2: break
            self.log_text.delete(rngs[0], rngs[1])
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        line = f"[{ts}] {msg}\n"
        self.log_text.insert(tk.END, line, "bet_info")
        self.log_text.see(tk.END)

    # ------------------------------------------------------------
    # 注数 / 金额计算（按 Spinbox 参数，与池无关）
    # ------------------------------------------------------------
    def _calc_dantuo_bets(self):
        """返回 (前区注数, 后区注数, 总注数, 总金额)。按 Spinbox 参数计算，与号码池/输入框内容无关。"""
        try:
            dfc = safe_int(self.dan_front_count.get(), 0)
            tfc = safe_int(self.dan_tuo_count.get(), 0)
            dbc = safe_int(self.dan_back_count.get(), 0)
            tbc = safe_int(self.dan_back_tuo_count.get(), 0)
        except Exception:
            return 0, 0, 0, 0
        # 前区注数
        if dfc >= 5:
            front_bets = 1
        else:
            need_f = 5 - dfc
            if tfc < need_f:
                front_bets = 0
            else:
                try: front_bets = comb(tfc, need_f)
                except Exception: front_bets = 0
        # 后区注数
        if dbc >= 2:
            back_bets = 1
        else:
            need_b = 2 - dbc
            if tbc < need_b:
                back_bets = 0
            else:
                try: back_bets = comb(tbc, need_b)
                except Exception: back_bets = 0
        total = front_bets * back_bets
        return front_bets, back_bets, total, total * UNIT_PRICE

    def _calc_fushi_bets(self):
        """返回 (前区注数, 后区注数, 总注数, 总金额)。按 Spinbox 参数计算，与池无关。"""
        try:
            fc = safe_int(self.fu_front.get(), 5)
            bc = safe_int(self.fu_back.get(), 2)
        except Exception:
            return 0, 0, 0, 0
        if fc < 5: fc = 5
        if bc < 2: bc = 2
        try: front_bets = comb(fc, 5)
        except Exception: front_bets = 0
        try: back_bets = comb(bc, 2)
        except Exception: back_bets = 0
        total = front_bets * back_bets
        return front_bets, back_bets, total, total * UNIT_PRICE

    def calc_and_show_bet_info(self):
        """按当前 Notebook 页，把注数/金额覆盖式更新到日志区。"""
        try:
            tab = self.nb.tab(self.nb.select(), "text")
        except Exception:
            return
        if "胆拖" in tab:
            fb, bb, total, amount = self._calc_dantuo_bets()
            dfc = safe_int(self.dan_front_count.get(), 0)
            tfc = safe_int(self.dan_tuo_count.get(), 0)
            dbc = safe_int(self.dan_back_count.get(), 0)
            tbc = safe_int(self.dan_back_tuo_count.get(), 0)
            if total <= 0:
                msg = (f"💰 胆拖：红胆{dfc}+红拖{tfc} / 蓝胆{dbc}+蓝拖{tbc} → 参数不足，无法组成单注")
            else:
                msg = (f"💰 胆拖：红胆{dfc}+红拖{tfc}（前区{fb}注） / "
                       f"蓝胆{dbc}+蓝拖{tbc}（后区{bb}注） → 共 {total} 注，金额 {amount} 元")
        elif "复式" in tab:
            fb, bb, total, amount = self._calc_fushi_bets()
            fc = safe_int(self.fu_front.get(), 5); bc = safe_int(self.fu_back.get(), 2)
            msg = (f"💰 复式：前区{fc}个（{fb}注） / 后区{bc}个（{bb}注） → "
                   f"共 {total} 注，金额 {amount} 元")
        else:
            n = safe_int(self.ticket_spin.get(), 1)
            if n <= 0: n = 1
            msg = f"💰 普通预测：{n} 注，金额 {n * UNIT_PRICE} 元"
        self._update_bet_log_line(msg)

    def _on_pool_mode_change(self):
        mode = self.front_pool_mode.get()
        if mode == "down":
            self.log("📌 已切换为【下号池选号】（对号下号法）")
        else:
            self.log("📌 已切换为【全号池选号】")

    def build_ui(self):
        top = tk.Frame(self.root, bg=COLORS["bg_top"], height=290)
        top.pack(fill=tk.X, padx=10, pady=(10, 5)); top.pack_propagate(False)
        r1 = tk.Frame(top, bg=COLORS["bg_top"]); r1.pack(pady=(8, 2))
        for t, cmd in [("🔍 联网查询", self.fetch_online), ("📂 导入Excel", self.import_excel),
                       ("⬇ 更新数据", self.update_data), ("🎯 预测号码", self.predict_numbers),
                       ("💾 保存结果", self.save_results), ("🤖 AI预测", self.toggle_ai),
                       ("📝 反馈", self.feedback), ("📊 图表", self.show_chart),
                       ("🛠 数据管理", self.data_manage), ("🧠 智能组号", self.smart_group),
                       ("⚙️ AI设置", self.ai_settings)]:
            if t == "🎯 预测号码":
                btn = RoundedButton(r1, text=t, command=cmd, width=88, height=28,
                                    bg="#E74C3C", fg="black",
                                    font=("微软雅黑", 9, "bold"),
                                    parent_bg=COLORS["bg_top"])
            else:
                btn = RoundedButton(r1, text=t, command=cmd, width=88, height=28, parent_bg=COLORS["bg_top"])
            btn.pack(side=tk.LEFT, padx=2)
            if t == "🎯 预测号码": self.predict_btn = btn
        r2 = tk.Frame(top, bg=COLORS["bg_top"]); r2.pack(pady=(4, 2))
        tk.Label(r2, text="数据源:", bg=COLORS["bg_top"]).pack(side=tk.LEFT, padx=5)
        src = ttk.Combobox(r2, textvariable=self.data_source, values=["excel", "online", "merged"], state="readonly", width=10)
        src.pack(side=tk.LEFT); src.bind("<<ComboboxSelected>>", lambda e: self.refresh_source())
        tk.Label(r2, text="查询期数:", bg=COLORS["bg_top"]).pack(side=tk.LEFT, padx=15)
        self.query_spin = tk.Spinbox(r2, from_=1, to=50, width=5); self.query_spin.pack(side=tk.LEFT)
        self.query_spin.delete(0, tk.END); self.query_spin.insert(0, "20")
        tk.Label(r2, text="注数:", bg=COLORS["bg_top"]).pack(side=tk.LEFT, padx=15)
        # 注数档位：5/10 常规；17/20/34/50 为覆盖率档（34 注≈90%，68 元）
        self.ticket_spin = ttk.Combobox(r2, values=[1,2,3,4,5,6,7,8,9,10,
                                                    15,17,20,25,30,34,40,50], width=3, state="readonly")
        self.ticket_spin.pack(side=tk.LEFT); self.ticket_spin.current(9)  # 默认 10 注
        self.ticket_spin.bind("<<ComboboxSelected>>", lambda e: self.calc_and_show_bet_info())
        tk.Label(r2, text="服务器:", bg=COLORS["bg_top"]).pack(side=tk.LEFT, padx=15)
        self.server_cb = ttk.Combobox(r2, values=[s["name"] for s in self.servers], width=18, state="readonly")
        self.server_cb.pack(side=tk.LEFT); self.server_cb.current(0)
        nb = ttk.Notebook(top); nb.pack(pady=(5, 0), fill='x')
        self.nb = nb

        # ---------------- 普通预测 ----------------
        self.norm_frame = tk.Frame(nb, bg=COLORS["bg_top"])
        tk.Label(self.norm_frame, text="前区:", bg=COLORS["bg_top"]).pack(side=tk.LEFT, padx=5)
        self.norm_front = tk.Entry(self.norm_frame, width=22); self.norm_front.pack(side=tk.LEFT, padx=3); add_right_click_menu(self.norm_front)
        tk.Label(self.norm_frame, text="后区:", bg=COLORS["bg_top"]).pack(side=tk.LEFT, padx=5)
        self.norm_back = tk.Entry(self.norm_frame, width=12); self.norm_back.pack(side=tk.LEFT); add_right_click_menu(self.norm_back)
        tk.Label(self.norm_frame, text="选号池:", bg=COLORS["bg_top"], font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=(12, 2))
        tk.Radiobutton(self.norm_frame, text="下号池", variable=self.front_pool_mode,
                       value="down", bg=COLORS["bg_top"], activebackground=COLORS["bg_top"],
                       font=("微软雅黑", 9), command=self._on_pool_mode_change).pack(side=tk.LEFT)
        tk.Radiobutton(self.norm_frame, text="全号池", variable=self.front_pool_mode,
                       value="full", bg=COLORS["bg_top"], activebackground=COLORS["bg_top"],
                       font=("微软雅黑", 9), command=self._on_pool_mode_change).pack(side=tk.LEFT)
        self.norm_bet_label = tk.Label(self.norm_frame, text="", bg=COLORS["bg_top"],
                                       fg="#B8860B", font=("微软雅黑", 9, "bold"))
        self.norm_bet_label.pack(side=tk.LEFT, padx=12)
        nb.add(self.norm_frame, text="普通预测")

        # ---------------- 胆拖选号 ----------------
        self.dan_frame = tk.Frame(nb, bg=COLORS["bg_top"])
        dan_entries = []
        for label, width, attr in [("红胆:", 12, "red_dan"), ("红拖:", 18, "red_tuo"), ("蓝胆:", 8, "blue_dan"), ("蓝拖:", 12, "blue_tuo")]:
            tk.Label(self.dan_frame, text=label, bg=COLORS["bg_top"]).pack(side=tk.LEFT, padx=3)
            entry = tk.Entry(self.dan_frame, width=width); entry.pack(side=tk.LEFT, padx=2)
            add_right_click_menu(entry); setattr(self, attr, entry)
            dan_entries.append(entry)
        spin_vars = []
        for label, var, default, from_, to in [("红胆个数:", "dan_front_count", "2", 0, 5),
                                                ("红拖个数:", "dan_tuo_count", "8", 0, 20),
                                                ("蓝胆个数:", "dan_back_count", "1", 0, 2),
                                                ("蓝拖个数:", "dan_back_tuo_count", "3", 0, 12)]:
            tk.Label(self.dan_frame, text=label, bg=COLORS["bg_top"], font=("微软雅黑", 8)).pack(side=tk.LEFT, padx=(10, 2))
            sp = tk.Spinbox(self.dan_frame, from_=from_, to=to, width=3, font=("微软雅黑", 9))
            sp.pack(side=tk.LEFT, padx=2); sp.delete(0, tk.END); sp.insert(0, default)
            setattr(self, var, sp); spin_vars.append(sp)
        self.dan_bet_label = tk.Label(self.dan_frame, text="", bg=COLORS["bg_top"],
                                      fg="#B8860B", font=("微软雅黑", 9, "bold"))
        self.dan_bet_label.pack(side=tk.LEFT, padx=10)
        nb.add(self.dan_frame, text="胆拖选号")
        for sp in spin_vars:
            sp.bind("<KeyRelease>", lambda e: self.calc_and_show_bet_info())
            sp.bind("<ButtonRelease-1>", lambda e: self.calc_and_show_bet_info())
            sp.bind("<<Increment>>", lambda e: self.root.after(50, self.calc_and_show_bet_info))
            sp.bind("<<Decrement>>", lambda e: self.root.after(50, self.calc_and_show_bet_info))
            sp.bind("<FocusOut>", lambda e: self.calc_and_show_bet_info())
        for entry in dan_entries:
            entry.bind("<KeyRelease>", lambda e: self.calc_and_show_bet_info())
            entry.bind("<FocusOut>", lambda e: self.calc_and_show_bet_info())

        # ---------------- 复式选号 ----------------
        self.fu_frame = tk.Frame(nb, bg=COLORS["bg_top"])
        tk.Label(self.fu_frame, text="红球个数(5-18):", bg=COLORS["bg_top"]).pack(side=tk.LEFT, padx=5)
        self.fu_front = tk.Spinbox(self.fu_frame, from_=5, to=18, width=5); self.fu_front.pack(side=tk.LEFT)
        self.fu_front.delete(0, tk.END); self.fu_front.insert(0, "5")
        tk.Label(self.fu_frame, text="蓝球个数(2-12):", bg=COLORS["bg_top"]).pack(side=tk.LEFT, padx=10)
        self.fu_back = tk.Spinbox(self.fu_frame, from_=2, to=12, width=5); self.fu_back.pack(side=tk.LEFT)
        self.fu_back.delete(0, tk.END); self.fu_back.insert(0, "2")
        self.fu_bet_label = tk.Label(self.fu_frame, text="", bg=COLORS["bg_top"],
                                     fg="#B8860B", font=("微软雅黑", 9, "bold"))
        self.fu_bet_label.pack(side=tk.LEFT, padx=15)
        nb.add(self.fu_frame, text="复式选号")
        for sp in (self.fu_front, self.fu_back):
            sp.bind("<KeyRelease>", lambda e: self.calc_and_show_bet_info())
            sp.bind("<ButtonRelease-1>", lambda e: self.calc_and_show_bet_info())
            sp.bind("<<Increment>>", lambda e: self.root.after(50, self.calc_and_show_bet_info))
            sp.bind("<<Decrement>>", lambda e: self.root.after(50, self.calc_and_show_bet_info))
            sp.bind("<FocusOut>", lambda e: self.calc_and_show_bet_info())

        nb.bind("<<NotebookTabChanged>>", lambda e: self.root.after(50, self._refresh_all_bet_labels))

        # ---------------- 杀号 / 断区 / 比例 ----------------
        kill_row = tk.Frame(top, bg=COLORS["bg_top"]); kill_row.pack(pady=(3, 2))
        tk.Label(kill_row, text="前区杀号:", bg=COLORS["bg_top"], font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=(5, 2))
        self.kill_front_entry = tk.Entry(kill_row, width=35, font=("微软雅黑", 9), relief=tk.FLAT, bg="white")
        self.kill_front_entry.pack(side=tk.LEFT, padx=4); add_right_click_menu(self.kill_front_entry)
        tk.Label(kill_row, text="后区杀号:", bg=COLORS["bg_top"], font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=(15, 2))
        self.kill_back_entry = tk.Entry(kill_row, width=20, font=("微软雅黑", 9), relief=tk.FLAT, bg="white")
        self.kill_back_entry.pack(side=tk.LEFT, padx=4); add_right_click_menu(self.kill_back_entry)
        r4 = tk.Frame(top, bg=COLORS["bg_top"]); r4.pack(pady=(3, 6))
        tk.Label(r4, text="断区:", bg=COLORS["bg_top"]).pack(side=tk.LEFT, padx=5)
        self.bz1 = tk.BooleanVar(); self.bz2 = tk.BooleanVar(); self.bz3 = tk.BooleanVar()
        for t, v in [("一区", self.bz1), ("二区", self.bz2), ("三区", self.bz3)]:
            tk.Checkbutton(r4, text=t, variable=v, bg=COLORS["bg_top"], selectcolor=COLORS["accent_green"]).pack(side=tk.LEFT, padx=3)
        tk.Label(r4, text="奇偶比:", bg=COLORS["bg_top"]).pack(side=tk.LEFT, padx=15)
        self.oe_entry = tk.Entry(r4, width=8); self.oe_entry.pack(side=tk.LEFT, padx=2); add_right_click_menu(self.oe_entry)
        self.oe_rec = tk.Label(r4, text="", bg=COLORS["bg_top"], fg="#666"); self.oe_rec.pack(side=tk.LEFT, padx=5)
        tk.Label(r4, text="区间比:", bg=COLORS["bg_top"]).pack(side=tk.LEFT, padx=15)
        self.zr_entry = tk.Entry(r4, width=8); self.zr_entry.pack(side=tk.LEFT, padx=2); add_right_click_menu(self.zr_entry)
        self.zr_rec = tk.Label(r4, text="", bg=COLORS["bg_top"], fg="#666"); self.zr_rec.pack(side=tk.LEFT, padx=5)
        self.ai_on = tk.BooleanVar()

        # ---------------- 主区 ----------------
        mpw = tk.PanedWindow(self.root, orient=tk.VERTICAL, sashwidth=5, bg=COLORS["border"])
        mpw.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        top_pw = tk.PanedWindow(mpw, orient=tk.HORIZONTAL, sashwidth=5, bg=COLORS["border"])
        hist = tk.LabelFrame(top_pw, text="📋 历史开奖", bg="white", font=("微软雅黑", 10, "bold"))
        cols = ("期号", "日期", "前1", "前2", "前3", "前4", "前5", "后1", "后2")
        self.tree = ttk.Treeview(hist, columns=cols, show="headings", height=18)
        for c, w in zip(cols, [70, 90, 45, 45, 45, 45, 45, 45, 45]):
            self.tree.heading(c, text=c); self.tree.column(c, width=w, anchor="center")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Scrollbar(hist, orient="vertical", command=self.tree.yview).pack(side=tk.RIGHT, fill=tk.Y)
        top_pw.add(hist, stretch="always")
        pred_frame = tk.LabelFrame(top_pw, text="🎯 预测号码", bg=COLORS["bg_predict"], fg="white", font=("微软雅黑", 10, "bold"))
        self.pred_text = scrolledtext.ScrolledText(pred_frame, wrap=tk.WORD, height=15, bg=COLORS["bg_predict"],
                                                   fg="#FFB3B3", font=("微软雅黑", 10, "bold"))
        self.pred_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5); add_right_click_menu(self.pred_text)
        top_pw.add(pred_frame, stretch="never", minsize=260)
        mpw.add(top_pw, stretch="always")
        log_frame = tk.LabelFrame(mpw, text="📊 日志/分析", bg=COLORS["bg_card"], font=("微软雅黑", 10, "bold"))
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=8, bg="#FAFAFA", font=("微软雅黑", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5); add_right_click_menu(self.log_text)
        self.log_text.tag_config('red_bold', foreground='red', font=('微软雅黑', 9, 'bold'))
        self.log_text.tag_config('blue_bold', foreground='blue', font=('微软雅黑', 9, 'bold'))
        self.log_text.tag_config('normal', foreground='black', font=('微软雅黑', 9))
        self.log_text.tag_config('bet_info', foreground='#B8860B', font=('微软雅黑', 9, 'bold'))
        mpw.add(log_frame, stretch="always")

        self.root.after(300, self._refresh_all_bet_labels)

    def _refresh_all_bet_labels(self):
        try:
            n = safe_int(self.ticket_spin.get(), 1)
            if n <= 0: n = 1
            self.norm_bet_label.config(text=f"共 {n} 注 / {n * UNIT_PRICE} 元")
        except Exception: pass
        try:
            fb, bb, total, amount = self._calc_dantuo_bets()
            if total > 0:
                self.dan_bet_label.config(text=f"共 {total} 注 / {amount} 元")
            else:
                self.dan_bet_label.config(text="参数不足")
        except Exception: pass
        try:
            fb, bb, total, amount = self._calc_fushi_bets()
            self.fu_bet_label.config(text=f"共 {total} 注 / {amount} 元")
        except Exception: pass
        self.calc_and_show_bet_info()

    def refresh_source(self):
        src = self.data_source.get()
        if src == "excel": self.current_records = fetch_records('excel_history')
        elif src == "online": self.current_records = fetch_records('online_latest')
        else: self.current_records = get_merged_records()
        self.update_table(); self.update_omission(); self.update_recommendations()
        self.ai_predictor = None

    def update_table(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        for r in self.current_records:
            self.tree.insert("", tk.END, values=[r['period'], r['date']] +
                            [f"{n:02d}" for n in r['front']] + [f"{n:02d}" for n in r['back']])

    def update_omission(self):
        if not self.current_records: return
        ana = OmissionAnalyzer(self.current_records); h, w, c, e = ana.get_tier_numbers()
        self.log("=" * 50)
        self.log(f"热: {format_numbers(sorted(h))}  温: {format_numbers(sorted(w))}")
        self.log(f"冷: {format_numbers(sorted(c))}  极冷: {format_numbers(sorted(e))}")
        self.log("=" * 50)

    def update_recommendations(self):
        if not self.current_records: return
        ana = OmissionAnalyzer(self.current_records)
        oe = ana.get_recommended_odd_even(); self.oe_rec.config(text=f"推荐 {oe[0]}:{oe[1]}")
        broken = [x for x, v in [(1, self.bz1.get()), (2, self.bz2.get()), (3, self.bz3.get())] if v]
        zr = ana.get_recommended_zone_ratio(broken_zones=broken)
        self.zr_rec.config(text=f"推荐 {zr[0]}:{zr[1]}:{zr[2]}")

    def predict_numbers(self):
        if not self.current_records: messagebox.showwarning("提示", "请先加载数据"); return
        tab = self.nb.tab(self.nb.select(), "text"); mode = 'normal'
        kwargs = {'use_ai': self.ai_on.get(), 'log_func': self.log}
        broken = [x for x, v in [(1, self.bz1.get()), (2, self.bz2.get()), (3, self.bz3.get())] if v]
        kwargs['broken_zones'] = broken
        oe_text = self.oe_entry.get().strip()
        kwargs['odd_even_ratio'] = parse_ratio(oe_text, 5) if oe_text else OmissionAnalyzer(self.current_records).get_recommended_odd_even()
        zr_text = self.zr_entry.get().strip()
        kwargs['zone_ratio'] = parse_ratio(zr_text, 5) if zr_text else OmissionAnalyzer(self.current_records).get_recommended_zone_ratio(broken_zones=broken)
        kwargs['kill_front'] = parse_numbers(self.kill_front_entry.get(), 35)
        kwargs['kill_back'] = parse_numbers(self.kill_back_entry.get(), 12)
        count = 1 if "胆拖" in tab or "复式" in tab else int(self.ticket_spin.get() or 5)
        if "胆拖" in tab:
            mode = 'dantuo'
            try:
                dfc, tfc = int(self.dan_front_count.get()), int(self.dan_tuo_count.get())
                dbc, tbc = int(self.dan_back_count.get()), int(self.dan_back_tuo_count.get())
            except: dfc = tfc = dbc = tbc = 0
            auto = dfc > 0 and tfc > 0 and self.original_tickets
            if auto:
                fc = Counter()
                for f, b in self.original_tickets: fc.update(f)
                fs = [n for n, _ in fc.most_common()]
                dan_f, tuo_f = fs[:dfc], fs[dfc:dfc+tfc]
            else:
                dan_f = parse_numbers(self.red_dan.get(), 35); tuo_f = parse_numbers(self.red_tuo.get(), 35)
            if auto and dbc > 0 and tbc > 0 and self.original_tickets:
                bc = Counter()
                for f, b in self.original_tickets: bc.update(b)
                bs = [n for n, _ in bc.most_common()]
                dan_b, tuo_b = bs[:dbc], bs[dbc:dbc+tbc]
            else:
                dan_b = parse_numbers(self.blue_dan.get(), 12); tuo_b = parse_numbers(self.blue_tuo.get(), 12)
            if auto:
                if len(dan_f) + len(tuo_f) < 5: messagebox.showwarning("提示", "自动分配的胆码+拖码不足5个"); return
                self.log(f"🤖 自动分配前区胆码：{format_numbers(dan_f)}，拖码：{format_numbers(tuo_f)}")
            elif not dan_f and not tuo_f:
                messagebox.showwarning("提示", "请填写胆拖码"); return
            kwargs.update(dantuo_front_dan=dan_f, dantuo_front_tuo=tuo_f, dantuo_back_dan=dan_b, dantuo_back_tuo=tuo_b)
        elif "复式" in tab:
            mode = 'fushi'
            try: fc, bc = int(self.fu_front.get()), int(self.fu_back.get())
            except: fc, bc = 5, 2
            kwargs.update(fushi_front_count=fc, fushi_back_count=bc)
            if self.original_tickets:
                fpool = set(); bpool = set()
                for f, b in self.original_tickets:
                    for n in f: fpool.add(n)
                    for n in b: bpool.add(n)
                kwargs['fushi_front_pool'] = sorted(fpool)
                kwargs['fushi_back_pool'] = sorted(bpool)
                self.log(f"📌 复式号码池（来自上次普通预测）：前区 {len(fpool)} 个 / 后区 {len(bpool)} 个")
            else:
                self.log("⚠️ 尚未生成普通预测号码池，复式将使用全号池 1-35 / 1-12")
                kwargs['fushi_front_pool'] = None
                kwargs['fushi_back_pool'] = None
        else:
            pool_mode = self.front_pool_mode.get()
            if pool_mode == "down":
                down_pool = build_pair_down_pool(self.current_records)
                if not down_pool:
                    messagebox.showerror("错误", "当前数据源无有效记录，无法构建下号池")
                    return
                self.log(f"🎯 下号池（{len(down_pool)}个）：{format_numbers(down_pool)}")
                kwargs['front_pool'] = down_pool
                kwargs['strict_pool'] = True
            else:
                self.log("📌 使用全号池 1-35 选号")
                kwargs['front_pool'] = None
                kwargs['strict_pool'] = False
            kwargs.update(manual_front=parse_numbers(self.norm_front.get(), 35),
                          manual_back=parse_numbers(self.norm_back.get(), 12))
        gen = NumberGenerator(self.current_records, mode=mode, **kwargs)
        if self.ai_on.get() and gen.ai_predictor and not gen.ai_predictor.models:
            self.log("🤖 正在后台训练AI模型...")
            self.predict_btn.configure(state="disabled")
            threading.Thread(target=lambda: self._train_and_predict(gen, mode, kwargs, count), daemon=True).start()
        else: self._do_predict(gen, mode, kwargs, count)

    def _train_and_predict(self, gen, mode, kwargs, count):
        try:
            gen.ai_predictor.train()
            with open(MODEL_PATH, 'wb') as f: pickle.dump(gen.ai_predictor, f)
            self.ai_predictor = gen.ai_predictor; self.ai_predictor.log_func = self.log
            self.log("✅ AI模型训练完成")
        except Exception as e: self.log(f"❌ 训练失败：{e}")
        finally:
            self.root.after(0, lambda: self.predict_btn.configure(state="normal"))
            self.root.after(0, lambda: self._do_predict(gen, mode, kwargs, count))

    def _do_predict(self, gen, mode, kwargs, count):
        try:
            # 候选池：多生成一些，再按覆盖率（注间重叠最小）择优，
            # 同等注数下提高"至少中一注"概率。
            # 实测候选池 ≥300 后覆盖率不再提升，取 300 兼顾速度。
            tickets = []; seen = set()
            cand_target = max(count * 30, 300) if count > 1 else 1
            tries = cand_target * 12
            while len(tickets) < cand_target and tries > 0:
                try: typ, front, back = gen.generate()
                except ValueError as e:
                    self.log(f"❌ 生成错误：{e}")
                    messagebox.showerror("错误", str(e))
                    return
                key = (tuple(front), tuple(back))
                if key not in seen:
                    seen.add(key); tickets.append((front, back))
                tries -= 1
            if not tickets: messagebox.showerror("错误", "无法生成不重复的号码"); return

            if count > 1 and len(tickets) > count:
                raw_overlap = cov.total_overlap(tickets[:count])
                tickets = cov.optimize(tickets, count)
                opt_overlap = cov.total_overlap(tickets)
                gain = cov.prob_at_least_one(count)
                self.log(f"🎯 覆盖率优化：{count} 注，注间重叠 {raw_overlap:.0f} → {opt_overlap:.0f}"
                         f"（独立理论上限 {gain*100:.1f}%，减少重复覆盖）")
            else:
                tickets = tickets[:count]
            self.last_tickets = tickets.copy()
            if mode == 'normal': self.original_tickets = tickets.copy()

            extra_info = None
            if mode == 'dantuo':
                extra_info = {
                    'red_dan': list(kwargs.get('dantuo_front_dan', [])),
                    'red_tuo': list(kwargs.get('dantuo_front_tuo', [])),
                    'blue_dan': list(kwargs.get('dantuo_back_dan', [])),
                    'blue_tuo': list(kwargs.get('dantuo_back_tuo', []))
                }
            save_predictions(tickets, mode=mode, extra_info=extra_info)

            self.pred_text.delete(1.0, tk.END)
            if mode == 'dantuo':
                df = kwargs.get('dantuo_front_dan', []); tf = kwargs.get('dantuo_front_tuo', [])
                db = kwargs.get('dantuo_back_dan', []); tb = kwargs.get('dantuo_back_tuo', [])
                self.pred_text.insert(tk.END, "胆拖选号结果\n")
                self.pred_text.insert(tk.END, f"红胆码：{format_numbers(df)}\n红拖码：{format_numbers(tf)}\n")
                self.pred_text.insert(tk.END, f"蓝胆码：{format_numbers(db)}\n蓝拖码：{format_numbers(tb)}\n")
                fb, bb, total, amount = self._calc_dantuo_bets()
                self.pred_text.insert(tk.END, f"\n注数：{total} 注\n金额：{amount} 元\n")
                self.log(f"🎯 胆拖：红胆{format_numbers(df)} 红拖{format_numbers(tf)} 蓝胆{format_numbers(db)} 蓝拖{format_numbers(tb)}")
                self.log(f"💰 胆拖注数 {total} 注，金额 {amount} 元")
            elif mode == 'fushi':
                self.pred_text.insert(tk.END, f"复式选号结果\n前区({len(tickets[0][0])}个)：{format_numbers(tickets[0][0])}\n后区({len(tickets[0][1])}个)：{format_numbers(tickets[0][1])}\n")
                fb, bb, total, amount = self._calc_fushi_bets()
                self.pred_text.insert(tk.END, f"\n注数：{total} 注\n金额：{amount} 元\n")
                self.log(f"🎯 复式：前区{format_numbers(tickets[0][0])} 后区{format_numbers(tickets[0][1])}")
                self.log(f"💰 复式注数 {total} 注，金额 {amount} 元")
            else:
                total = len(tickets); amount = total * UNIT_PRICE
                pool_mode = self.front_pool_mode.get()
                pool_desc = "对号下号法（下号池）" if pool_mode == "down" else "全号池（1-35）"
                self.pred_text.insert(tk.END, f"预测号码 共{total}注 / 金额 {amount} 元\n")
                self.pred_text.insert(tk.END, f"📌 号码来源：{pool_desc}\n")
                self.pred_text.insert(tk.END, f"📊 至少中一注概率（估算）：{cov.coverage_score(tickets)*100:.1f}%"
                                              f"（独立上限 {cov.prob_at_least_one(total)*100:.1f}%）\n")
                if total >= 10:
                    self.pred_text.insert(tk.END, f"📌 10 注已封顶：这是 10 注能到的最高覆盖率，"
                                                  f"再多需超过上限\n")
                self.pred_text.insert(tk.END, f"{'='*30}\n")
                for i, (f, b) in enumerate(tickets, 1):
                    self.pred_text.insert(tk.END, f"第{i:02d}注 前区：{format_numbers(f)}  后区：{format_numbers(b)}\n")
                self.log(f"🎯 预测完成，共 {total} 注，金额 {amount} 元。")
                self.log(f"📊 至少中一注估算 {cov.coverage_score(tickets)*100:.1f}%"
                         f"（单注 {cov.P_SINGLE_WIN*100:.2f}%，"
                         f"90% 需 {cov.tickets_for_target(0.90)} 注但已受 10 注上限约束）")
                self.root.after(100, self._refresh_all_bet_labels)
                self._llm_assist(tickets, count)
        except Exception as e:
            self.log(f"❌ 预测异常：{e}"); messagebox.showerror("错误", f"预测失败：{e}")

    # ------------------------------------------------------------
    # 免费大模型辅助·二次选号（不影响基础结果，后台增强）
    # ------------------------------------------------------------
    def _llm_assist(self, tickets, count):
        """普通预测后，若启用了免费AI模型，用它做一次较“聪明”的选号建议。"""
        if not (self.ai_cfg and self.ai_cfg.enabled):
            return
        if not tickets:
            return
        # 前半段——统计特征摘要
        recent = self.current_records[:20]
        hot = Counter()
        for r in recent:
            hot.update(r['front'])
        hot_str = " ".join(f"{n}:{c}" for n, c in hot.most_common(8))
        cold = [n for n in range(1, 36) if hot[n] == 0][:8]
        prompt = (
            f"请仅输出5个1-35的前区号码和2个1-12的后区号码，共一组，用空格隔开（格式：前区 后区）。\n"
            f"参考最近热号(近20期出现次数)：{hot_str}\n"
            f"冷号：{' '.join(map(str, cold))}\n"
            f"上一组预测：{format_numbers(tickets[0][0])} + {format_numbers(tickets[0][1])}\n"
        )
        def done(ok, text):
            if not ok:
                self.log("ℹ️ 免费AI未能调用，本次仅用本地统计预测")
                return
            nums = lai.extract_numbers(text)
            front = lai.validate_numbers(nums, 1, 35, 5)
            back = lai.validate_numbers(nums, 1, 12, 2)
            r = self._validate_llm_result(front, back)
            if r:
                self.log(f"🤖 免费AI建议：前区{format_numbers(front)}  后区{format_numbers(back)}（已校验合法）")
                self.pred_text.insert(tk.END, "\n🤖 AI模型建议（仅供参考）：\n")
                self.pred_text.insert(tk.END,
                    f"前区：{format_numbers(front)}  后区：{format_numbers(back)}\n")
                self.pred_text.insert(tk.END, "⚠️ 注：模型输出仅为随机性参考，不构成中奖保证。\n")
            else:
                self.log("ℹ️ 免费AI建议号码未通过校验，忽略")
        lai.chat_async(self.ai_cfg, prompt, done, log=self.log)

    def _validate_llm_result(self, front, back):
        if len(front) != 5 or len(back) != 2:
            return False
        if len(set(front)) != 5 or len(set(back)) != 2:
            return False
        if any(n < 1 or n > 35 for n in front):
            return False
        if any(n < 1 or n > 12 for n in back):
            return False
        return True

    def smart_group(self):
        if not self.original_tickets: messagebox.showwarning("提示", "请先进行普通预测生成号码池"); return
        if len(self.original_tickets) < 2: messagebox.showinfo("提示", "只有1注号码，无需重组"); return
        validator = NumberGenerator(self.current_records or [], mode='normal')._validate_front
        n = len(self.original_tickets)
        cand = smart_regroup(self.original_tickets, validator=validator,
                             target_count=max(n * 12, 60))
        if cand and len(cand) > n:
            raw_ov = cov.total_overlap(cand[:n])
            new_tickets = cov.optimize(cand, n, seed=None)
            self.log(f"🎯 智能组号覆盖率优化：重叠 {raw_ov:.0f} → {cov.total_overlap(new_tickets):.0f}")
        else:
            new_tickets = cand or self.original_tickets
        self.pred_text.delete(1.0, tk.END)
        self.pred_text.insert(tk.END, f"智能重组号码 共{len(new_tickets)}注 / 金额 {len(new_tickets)*UNIT_PRICE} 元\n{'='*30}\n")
        for i, (f, b) in enumerate(new_tickets, 1):
            self.pred_text.insert(tk.END, f"第{i:02d}注 前区：{format_numbers(f)}  后区：{format_numbers(b)}\n")
        save_predictions(new_tickets); self.last_tickets = new_tickets
        self.log(f"🧠 智能组号完成，共 {len(new_tickets)} 注，金额 {len(new_tickets)*UNIT_PRICE} 元")

    def fetch_online(self):
        idx = self.server_cb.current()
        if idx < 0: return
        server = self.servers[idx]; count = int(self.query_spin.get())
        self.log("🔍 正在获取联网数据...")
        def do():
            try:
                data = DataFetcher.fetch_from_server(server, count)
                if data:
                    records = DataFetcher.parse_response(data, server.get("type", "sporttery"))
                    if not records:
                        reason = DataFetcher.last_error or "返回数据为空或格式不符"
                        self.root.after(0, lambda r=reason: [self.log(f"❌ 联网取数失败：{r}"),
                                                              messagebox.showerror("错误", f"取数失败：{r}")])
                        return
                    clear_table('online_latest')
                    for r in records: insert_record('online_latest', r['period'], r['date'], r['front'], r['back'])

                    def _apply():
                        # 自动切到 online 数据源，否则界面仍显示空的 excel 表
                        self.data_source.set("online")
                        self.refresh_source()
                        self.log(f"✅ 联网更新 {len(records)} 条（数据源已切换为 online）")
                    self.root.after(0, _apply)
                else:
                    reason = DataFetcher.last_error or "未知原因"
                    self.root.after(0, lambda r=reason: [self.log(f"❌ 网络请求失败：{r}"),
                                                          messagebox.showerror("错误", f"网络请求失败：{r}")])
            except Exception as e: self.root.after(0, lambda: self.log(f"❌ 联网出错：{e}"))
        threading.Thread(target=do, daemon=True).start()

    def import_excel(self):
        filepath = filedialog.askopenfilename(filetypes=[("Excel文件", "*.xlsx *.xls")])
        if not filepath: return
        try:
            df = pd.read_excel(filepath); records = []
            dc = pc = fc = bc = None
            for col in df.columns:
                cl = str(col).lower().strip()
                if "日期" in cl or "date" in cl: dc = col
                elif "期号" in cl or "period" in cl: pc = col
                elif "前区" in cl or "front" in cl: fc = col
                elif "后区" in cl or "back" in cl: bc = col
            if not all([dc, pc, fc, bc]) and len(df.columns) >= 4:
                dc, pc, fc, bc = df.columns[:4]
            for _, row in df.iterrows():
                front = parse_numbers(str(row.get(fc, "")), 35, 5)
                back = parse_numbers(str(row.get(bc, "")), 12, 2)
                if front and back: records.append({"period": str(row.get(pc, "")), "date": str(row.get(dc, "")), "front": front, "back": back})
            cnt = 0
            for r in records: insert_record('excel_history', r['period'], r['date'], r['front'], r['back']); cnt += 1
            self.log(f"📂 Excel导入 {cnt} 条"); self.refresh_source()
        except Exception as e: messagebox.showerror("错误", f"Excel读取失败：{e}")

    def update_data(self): self.fetch_online()

    def save_results(self):
        content = self.pred_text.get(1.0, tk.END).strip()
        if not content: messagebox.showwarning("提示", "没有可保存的预测结果"); return
        fp = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("文本文件", "*.txt")])
        if fp:
            with open(fp, "w", encoding="utf-8") as f: f.write(content)
            messagebox.showinfo("成功", f"已保存至 {fp}")

    def toggle_ai(self):
        self.ai_on.set(not self.ai_on.get())
        self.log("🤖 AI预测已" + ("开启" if self.ai_on.get() else "关闭"))

    def insert_highlighted_numbers(self, text_widget, front_nums, back_nums, hf_set, hb_set):
        text_widget.insert(tk.END, "前区：", 'normal')
        for num in front_nums:
            text_widget.insert(tk.END, f"{num:02d} ", 'red_bold' if num in hf_set else 'normal')
        text_widget.insert(tk.END, "  后区：", 'normal')
        for num in back_nums:
            text_widget.insert(tk.END, f"{num:02d} ", 'blue_bold' if num in hb_set else 'normal')
        text_widget.insert(tk.END, "\n", 'normal')

    def log_comparison(self, pf, pb, af, ab):
        self.log_text.insert(tk.END, "\n📝 对比结果：", 'normal')
        self.insert_highlighted_numbers(self.log_text, pf, pb, set(af), set(ab))
        self.log_text.insert(tk.END, "实际开奖：前区 ", 'normal')
        for num in af: self.log_text.insert(tk.END, f"{num:02d} ", 'normal')
        self.log_text.insert(tk.END, "后区 ", 'normal')
        for num in ab: self.log_text.insert(tk.END, f"{num:02d} ", 'normal')
        self.log_text.insert(tk.END, "\n", 'normal')

    def feedback(self):
        unfed = get_prediction_groups(0); fed = get_prediction_groups(1)
        if not unfed and not fed: messagebox.showinfo("提示", "没有任何预测记录"); return
        dlg = tk.Toplevel(self.root, bg=COLORS["bg_main"])
        dlg.title("反馈管理"); dlg.geometry("620x600")
        try: dlg.iconbitmap(resource_path("app.ico"))
        except: pass
        nb = ttk.Notebook(dlg); nb.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        all_periods = get_all_periods(); default_period = all_periods[0] if all_periods else ""

        def cfg_tags(w):
            w.tag_config('red_bold', foreground='red', font=('微软雅黑', 9, 'bold'))
            w.tag_config('blue_bold', foreground='blue', font=('微软雅黑', 9, 'bold'))
            w.tag_config('normal', foreground='black', font=('微软雅黑', 9))
            w.tag_config('mode_tag', foreground='#B8860B', font=('微软雅黑', 9, 'bold'))

        def show_dantuo_info(widget, pmode, einfo):
            if pmode == 'dantuo' and einfo:
                try:
                    info = json.loads(einfo)
                    w_rd = format_numbers(info.get('red_dan', []))
                    w_rt = format_numbers(info.get('red_tuo', []))
                    w_bd = format_numbers(info.get('blue_dan', []))
                    w_bt = format_numbers(info.get('blue_tuo', []))
                    widget.insert(tk.END,
                        f"[胆拖] 红胆:{w_rd}  红拖:{w_rt}  蓝胆:{w_bd}  蓝拖:{w_bt}\n",
                        'mode_tag')
                except Exception:
                    pass
            elif pmode == 'fushi':
                widget.insert(tk.END, "[复式] ", 'mode_tag')

        # 未反馈
        uf = tk.Frame(nb, bg=COLORS["bg_main"]); nb.add(uf, text="📝 未反馈")
        tk.Label(uf, text="选择要反馈的预测组:", font=("微软雅黑", 10, "bold"), bg=COLORS["bg_main"]).pack(pady=5)
        lf = tk.Frame(uf, bg=COLORS["bg_main"]); lf.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        sb = ttk.Scrollbar(lf); sb.pack(side=tk.RIGHT, fill=tk.Y)
        ul = tk.Listbox(lf, font=("微软雅黑", 9), yscrollcommand=sb.set, height=6)
        for gid, ts in unfed: ul.insert(tk.END, f"{ts}")
        ul.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sb.config(command=ul.yview)
        pf = tk.Frame(uf, bg=COLORS["bg_main"]); pf.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(pf, text="选择开奖期号:", bg=COLORS["bg_main"], font=("微软雅黑", 9)).pack(side=tk.LEFT)
        upv = tk.StringVar(value=default_period)
        ttk.Combobox(pf, textvariable=upv, values=all_periods, width=15, state="readonly").pack(side=tk.LEFT, padx=5)
        df_ = tk.LabelFrame(uf, text="该组预测号码", bg=COLORS["bg_main"], font=("微软雅黑", 9)); df_.pack(fill=tk.BOTH, padx=10, pady=5)
        udt = scrolledtext.ScrolledText(df_, height=8, font=("微软雅黑", 9), bg="white"); udt.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        cfg_tags(udt); add_right_click_menu(udt)
        sel = {"gid": None}

        def on_uf(evt=None):
            s = ul.curselection()
            if s:
                gid = unfed[s[0]][0]; sel["gid"] = gid
                preds = get_group_predictions(gid); udt.delete(1.0, tk.END)
                af = parse_numbers(ufe.get(), 35, 5) if ufe.get().strip() else []
                ab = parse_numbers(ube.get(), 12, 2) if ube.get().strip() else []
                af_set, ab_set = set(af), set(ab)
                for row in preds:
                    pid, front, back, pmode, einfo = row
                    fn = list(map(int, front.split())); bn = list(map(int, back.split()))
                    udt.insert(tk.END, f"ID:{pid}  ", 'normal')
                    show_dantuo_info(udt, pmode, einfo)
                    if len(fn) > 5 or len(bn) > 2:
                        udt.insert(tk.END, f"前区{len(fn)}个：", 'normal')
                        for n in fn: udt.insert(tk.END, f"{n:02d} ", 'red_bold' if n in af_set else 'normal')
                        udt.insert(tk.END, f"  后区{len(bn)}个：", 'normal')
                        for n in bn: udt.insert(tk.END, f"{n:02d} ", 'blue_bold' if n in ab_set else 'normal')
                        udt.insert(tk.END, "\n", 'normal')
                    else:
                        self.insert_highlighted_numbers(udt, fn, bn, af_set, ab_set)
        ul.bind('<<ListboxSelect>>', on_uf)
        inp = tk.Frame(uf, bg=COLORS["bg_main"]); inp.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(inp, text="真实前区:", bg=COLORS["bg_main"], font=("微软雅黑", 9)).pack(side=tk.LEFT)
        ufv = tk.StringVar(); ufe = tk.Entry(inp, width=25, textvariable=ufv); ufe.pack(side=tk.LEFT, padx=5); add_right_click_menu(ufe)
        tk.Label(inp, text="后区:", bg=COLORS["bg_main"], font=("微软雅黑", 9)).pack(side=tk.LEFT)
        ubv = tk.StringVar(); ube = tk.Entry(inp, width=10, textvariable=ubv); ube.pack(side=tk.LEFT, padx=5); add_right_click_menu(ube)
        def load_uf():
            d = get_draw_by_period(upv.get())
            if d:
                ufv.set(format_numbers(d['front'])); ubv.set(format_numbers(d['back']))
                if sel["gid"]: on_uf()
        if default_period: load_uf()

        def submit_uf():
            gid = sel.get("gid")
            if not gid: messagebox.showwarning("提示", "请选择一组预测"); return
            af = parse_numbers(ufe.get(), 35, 5); ab = parse_numbers(ube.get(), 12, 2)
            if not af or not ab: messagebox.showwarning("格式错误", "号码格式不正确"); return
            self.log(f"📝 反馈对比 [{gid}]：")
            for row in get_group_predictions(gid):
                pid, pfs, pbs = row[0], row[1], row[2]
                pf_ = list(map(int, pfs.split())); pb_ = list(map(int, pbs.split()))
                hf, hb = update_feedback(pid, af, ab)
                pn, pa, cond = get_prize_info(hf, hb)
                if pa == "浮动": ps = f"{pn}（{cond}）（浮动）"
                elif pa == 0: ps = "未中奖"
                else: ps = f"{pn}（{cond}）（{pa}元）"
                self.log(f"  第{pid}注：前区中{hf}个，后区中{hb}个 → {ps}")
                self.log_comparison(pf_, pb_, af, ab)
            new_uf = get_prediction_groups(0); ul.delete(0, tk.END)
            for gid, ts in new_uf: ul.insert(tk.END, f"{ts}")
            new_fd = get_prediction_groups(1); fl.delete(0, tk.END)
            for gid, ts in new_fd: fl.insert(tk.END, f"{ts}")
            messagebox.showinfo("成功", "反馈已提交")
        tk.Button(uf, text="提交反馈并学习", command=submit_uf, bg=COLORS["accent_green"], fg="white", font=("微软雅黑", 10)).pack(pady=10)

        # 已反馈
        ff = tk.Frame(nb, bg=COLORS["bg_main"]); nb.add(ff, text="✅ 已反馈")
        tk.Label(ff, text="已反馈的预测组（可重新对比）:", font=("微软雅黑", 10, "bold"), bg=COLORS["bg_main"]).pack(pady=5)
        flf = tk.Frame(ff, bg=COLORS["bg_main"]); flf.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        fsb = ttk.Scrollbar(flf); fsb.pack(side=tk.RIGHT, fill=tk.Y)
        fl = tk.Listbox(flf, font=("微软雅黑", 9), yscrollcommand=fsb.set, height=6)
        for gid, ts in fed: fl.insert(tk.END, f"{ts}")
        fl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); fsb.config(command=fl.yview)
        ffp = tk.Frame(ff, bg=COLORS["bg_main"]); ffp.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(ffp, text="选择开奖期号:", bg=COLORS["bg_main"], font=("微软雅黑", 9)).pack(side=tk.LEFT)
        fpv = tk.StringVar(value=default_period)
        ttk.Combobox(ffp, textvariable=fpv, values=all_periods, width=15, state="readonly").pack(side=tk.LEFT, padx=5)
        fdf = tk.LabelFrame(ff, text="详情与对比结果", bg=COLORS["bg_main"], font=("微软雅黑", 9)); fdf.pack(fill=tk.BOTH, padx=10, pady=5)
        fdt = scrolledtext.ScrolledText(fdf, height=10, font=("微软雅黑", 9), bg="white"); fdt.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        cfg_tags(fdt); add_right_click_menu(fdt)
        fip = tk.Frame(ff, bg=COLORS["bg_main"]); fip.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(fip, text="新真实前区:", bg=COLORS["bg_main"], font=("微软雅黑", 9)).pack(side=tk.LEFT)
        ffv = tk.StringVar(); ffe = tk.Entry(fip, width=25, textvariable=ffv); ffe.pack(side=tk.LEFT, padx=5); add_right_click_menu(ffe)
        tk.Label(fip, text="后区:", bg=COLORS["bg_main"], font=("微软雅黑", 9)).pack(side=tk.LEFT)
        fbv = tk.StringVar(); fbe = tk.Entry(fip, width=10, textvariable=fbv); fbe.pack(side=tk.LEFT, padx=5); add_right_click_menu(fbe)

        def on_fd(evt=None):
            s = fl.curselection()
            if s:
                gid = fed[s[0]][0]; preds = get_group_predictions(gid)
                fdt.delete(1.0, tk.END)
                fdt.insert(tk.END, f"📅 {fed[s[0]][1]}\n" + "─" * 40 + "\n", 'normal')
                af = parse_numbers(ffe.get(), 35, 5) if ffe.get().strip() else None
                ab = parse_numbers(fbe.get(), 12, 2) if fbe.get().strip() else None
                af_set = set(af) if af else set(); ab_set = set(ab) if ab else set()
                for row in preds:
                    pid, front, back, pmode, einfo = row
                    db_row = get_db().fetchone('SELECT actual_front, actual_back, hit_front, hit_back FROM predictions WHERE id=?', (pid,))
                    if db_row:
                        pf_ = list(map(int, front.split())); pb_ = list(map(int, back.split()))
                        actual_f = list(map(int, db_row[0].split())) if db_row[0] else None
                        actual_b = list(map(int, db_row[1].split())) if db_row[1] else None
                        fdt.insert(tk.END, f"ID:{pid}\n  预测：", 'normal')
                        show_dantuo_info(fdt, pmode, einfo)
                        if len(pf_) > 5 or len(pb_) > 2:
                            fdt.insert(tk.END, f"前区{len(pf_)}个：", 'normal')
                            for n in pf_: fdt.insert(tk.END, f"{n:02d} ", 'red_bold' if actual_f and n in actual_f else 'normal')
                            fdt.insert(tk.END, f"  后区{len(pb_)}个：", 'normal')
                            for n in pb_: fdt.insert(tk.END, f"{n:02d} ", 'blue_bold' if actual_b and n in actual_b else 'normal')
                            fdt.insert(tk.END, "\n", 'normal')
                        else:
                            self.insert_highlighted_numbers(fdt, pf_, pb_, set(actual_f) if actual_f else set(), set(actual_b) if actual_b else set())
                        if actual_f and actual_b:
                            fdt.insert(tk.END, f"  上次实际：前区 {db_row[0]}  后区 {db_row[1]}\n", 'normal')
                            pn, pa, cond = get_prize_info(db_row[2], db_row[3])
                            fdt.insert(tk.END, f"  上次结果：前区中{db_row[2]}个，后区中{db_row[3]}个 → {pn}（{cond}）\n", 'normal')
                        if af and ab:
                            hf = min(len(set(pf_) & af_set), 5); hb = min(len(set(pb_) & ab_set), 2)
                            pn, pa, cond = get_prize_info(hf, hb)
                            fdt.insert(tk.END, f"  新对比：前区中{hf}个，后区中{hb}个 → {pn}（{cond}）\n", 'normal')
                        fdt.insert(tk.END, "\n", 'normal')
        fl.bind('<<ListboxSelect>>', on_fd)

        def load_fd():
            d = get_draw_by_period(fpv.get())
            if d: ffv.set(format_numbers(d['front'])); fbv.set(format_numbers(d['back']))
        if default_period: load_fd()

        def recompare():
            s = fl.curselection()
            if s:
                af = parse_numbers(ffe.get(), 35, 5); ab = parse_numbers(fbe.get(), 12, 2)
                if not af or not ab: messagebox.showwarning("格式错误", "号码格式不正确"); return
                on_fd(); self.log(f"📝 已重新对比 [{fed[s[0]][0]}]")
        tk.Button(ff, text="重新对比", command=recompare, bg=COLORS["accent_blue"], fg="white", font=("微软雅黑", 10)).pack(pady=5)

    def show_chart(self):
        if not self.current_records: messagebox.showwarning("提示", "无数据"); return
        top = tk.Toplevel(self.root); top.title("遗漏走势")
        try: top.iconbitmap(resource_path("app.ico"))
        except: pass
        fig = Figure(figsize=(10, 4), dpi=100); ax = fig.add_subplot(111)
        ana = OmissionAnalyzer(self.current_records)
        nums = list(range(1, 36)); omissions = [ana.front_omission[n] for n in nums]
        ax.bar(nums, omissions, color='skyblue')
        ax.set_xlabel("号码"); ax.set_ylabel("遗漏期数"); ax.set_title("前区号码当前遗漏")
        canvas = FigureCanvasTkAgg(fig, master=top); canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def data_manage(self):
        dlg = tk.Toplevel(self.root); dlg.title("数据管理"); dlg.geometry("300x250")
        try: dlg.iconbitmap(resource_path("app.ico"))
        except: pass
        tk.Label(dlg, text=f"Excel数据：{get_record_count('excel_history')}条").pack(pady=5)
        tk.Label(dlg, text=f"联网数据：{get_record_count('online_latest')}条").pack(pady=5)
        tk.Button(dlg, text="清空Excel数据", command=lambda: [clear_table('excel_history'), self.refresh_source(), dlg.destroy()]).pack(pady=3)
        tk.Button(dlg, text="清空联网数据", command=lambda: [clear_table('online_latest'), self.refresh_source(), dlg.destroy()]).pack(pady=3)
        tk.Button(dlg, text="备份数据库", command=self.backup_db).pack(pady=3)
        tk.Button(dlg, text="恢复数据库", command=self.restore_db).pack(pady=3)

    def backup_db(self):
        dest = filedialog.asksaveasfilename(defaultextension=".db", filetypes=[("数据库文件", "*.db")])
        if dest: shutil.copy2(DB_PATH, dest); messagebox.showinfo("成功", "数据库已备份")

    def restore_db(self):
        src = filedialog.askopenfilename(filetypes=[("数据库文件", "*.db")])
        if src: shutil.copy2(src, DB_PATH); self.refresh_source(); messagebox.showinfo("成功", "数据库已恢复")

class DataFetcher:
    last_error = ""  # 记录最近一次失败原因，供 UI 展示

    @staticmethod
    def fetch_from_server(server, count):
        url = server['url']; params = server.get('params', {}).copy()
        if 'num' in params: params['num'] = str(count)
        elif 'pageSize' in params: params['pageSize'] = str(count)
        headers = {"User-Agent": "Mozilla/5.0"}
        DataFetcher.last_error = ""
        try:
            r = requests.get(url, params=params, headers=headers, timeout=10, verify=False)
            if r.status_code == 200:
                return r.json()
            DataFetcher.last_error = f"HTTP {r.status_code}：{r.text[:150]}"
        except requests.exceptions.Timeout:
            DataFetcher.last_error = "请求超时（10 秒），请检查网络或稍后重试"
        except requests.exceptions.ConnectionError:
            DataFetcher.last_error = "无法连接服务器（DNS 失败/被拦截/断网）"
        except requests.exceptions.RequestException as e:
            DataFetcher.last_error = f"请求异常：{type(e).__name__}: {e}"
        except Exception as e:
            DataFetcher.last_error = f"未知异常：{type(e).__name__}: {e}"
        return None

    @staticmethod
    def parse_response(data, api_type):
        records = []
        try:
            if api_type == 'jisuapi':
                # 极速数据业务错误（key 失效/次数用尽）会返回 status!=0
                if str(data.get('status', '0')) not in ('0', '200'):
                    DataFetcher.last_error = f"接口返回错误 status={data.get('status')} msg={data.get('msg', '')}"
                    return []
                for it in data.get('result', {}).get('list', []):
                    front = [int(x) for x in it.get('number', '').split() if x.isdigit()]
                    back = [int(x) for x in it.get('refernumber', '').split() if x.isdigit()]
                    if len(front) == 5 and len(back) == 2:
                        records.append({"period": it['issueno'], "date": it['opendate'], "front": front, "back": back})
            else:
                for it in data.get('value', {}).get('list', []):
                    parts = it.get('lotteryDrawResult', '').split()
                    if len(parts) >= 7:
                        front = [int(p) for p in parts[:5]]; back = [int(p) for p in parts[5:7]]
                        records.append({
                            "period": it.get('lotteryDrawNum', ''),
                            "date": it.get('lotteryDrawTime', ''),
                            "front": front, "back": back
                        })
        except Exception as e:
            DataFetcher.last_error = f"解析异常：{type(e).__name__}: {e}"
        return records

if __name__ == "__main__":
    root = tk.Tk()
    app = LottoApp(root)
    root.mainloop()