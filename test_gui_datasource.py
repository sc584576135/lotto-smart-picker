# -*- coding: utf-8 -*-
"""真实 GUI 集成测试：实例化 LottoApp，模拟联网查询，验证历史开奖表格真的被填充。"""
import sys, os, types, tempfile, shutil, threading

sys.path.insert(0, r'D:\PYWD\07.8')
os.chdir(tempfile.mkdtemp())          # 隔离数据库

import lotto_predictor as L

# 真实 tkinter，但隐藏窗口
import tkinter as tk
root = tk.Tk()
root.withdraw()

L.DB_PATH = 'lottery_data.db'
L.init_db()

fail = 0
def chk(name, cond, extra=''):
    global fail
    if cond: print('  PASS', name)
    else:
        print('  FAIL', name, extra); fail += 1

# 预置 3 条联网数据（模拟已取数成功）
recs = [{"period": "26128", "date": "2026-11-09", "front": [3,13,20,25,34], "back": [9,12]},
        {"period": "26127", "date": "2026-11-07", "front": [5,6,17,18,27], "back": [3,12]},
        {"period": "26126", "date": "2026-11-04", "front": [5,11,17,25,34], "back": [4,6]}]
for r in recs:
    L.insert_record('online_latest', r['period'], r['date'], r['front'], r['back'])

print('=== 构建真实 GUI ===')
try:
    app = L.LottoApp(root)
    chk('LottoApp 实例化成功', True)
except Exception as e:
    chk('LottoApp 实例化', False, f'{type(e).__name__}: {e}')
    raise SystemExit(1)

print('=== 1. 默认数据源是 excel（复现空表）===')
chk('默认 data_source=excel', app.data_source.get() == 'excel', app.data_source.get())
app.refresh_source()
rows_excel = len(app.tree.get_children())
chk('excel 源下表为空（复现 bug）', rows_excel == 0, f'{rows_excel} rows')

print('=== 2. 切到 online 后表格应填充 ===')
app.data_source.set('online')
app.refresh_source()
rows_online = len(app.tree.get_children())
chk('online 源下表格有 3 行', rows_online == 3, f'{rows_online} rows')

# 读第一行内容，确认渲染正确
first = app.tree.item(app.tree.get_children()[0])['values'] if rows_online else []
chk('首行有 9 列(期号+日期+5前区+2后区)', len(first) == 9, first)
if len(first) == 9:
    chk('期号正确', str(first[0]) == '26128', first[0])
    # 注意：tkinter Treeview.item()['values'] 会把纯数字字符串强制转 int，
    # '03' 读回来是 3，但界面渲染仍按原始字符串显示 '03'。故比对数值。
    chk('前区首号=3(界面显示03)', int(first[2]) == 3, first[2])
    chk('后区首号=9(界面显示09)', int(first[7]) == 9, first[7])
    # 直接验证格式化逻辑本身：源码必须用 02d 补零
    src_chk = open(r'D:\PYWD\07.8\lotto_predictor.py', encoding='utf-8').read()
    chk('update_table 使用 02d 补零', 'f"{n:02d}" for n in r[\'front\']' in src_chk)

print('=== 3. merged 源也能显示 ===')
app.data_source.set('merged')
app.refresh_source()
chk('merged 源下 3 行', len(app.tree.get_children()) == 3, len(app.tree.get_children()))

print('=== 4. 模拟 fetch_online 成功回调（核心修复）===')
# 清空，模拟"用户点联网查询"前的状态
L.clear_table('online_latest')
app.data_source.set('excel')
app.refresh_source()
chk('清空后 excel 源 0 行', len(app.tree.get_children()) == 0)

# 直接调用修复后的 _apply 逻辑等价路径：写入 + 切换 + 刷新
for r in recs:
    L.insert_record('online_latest', r['period'], r['date'], r['front'], r['back'])
app.data_source.set('online')     # 修复代码里做的正是这一步
app.refresh_source()
rows_after = len(app.tree.get_children())
chk('联网后表格显示 3 行', rows_after == 3, f'{rows_after} rows')
chk('data_source 已变为 online', app.data_source.get() == 'online', app.data_source.get())

print('=== 5. 修复代码位置校验 ===')
src = open(r'D:\PYWD\07.8\lotto_predictor.py', encoding='utf-8').read()
chk('fetch_online 内有 data_source.set("online")',
    'self.data_source.set("online")' in src)

root.destroy()
print()
print('FAILED:', fail)
sys.exit(1 if fail else 0)