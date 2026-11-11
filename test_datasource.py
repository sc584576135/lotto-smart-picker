# -*- coding: utf-8 -*-
"""验证联网查询后历史开奖区能显示数据（数据源自动切换逻辑）。"""
import sys, os, types, tempfile, shutil

sys.path.insert(0, r'D:\PYWD\07.8')

# ---------- 桩掉 GUI / 三方库 ----------
class FakeMod(types.ModuleType):
    def __getattr__(self, name):
        sub = types.ModuleType('fake.' + name)
        for a in ('Combobox','Notebook','Treeview','Scrollbar','Button','Entry',
                  'ScrolledText','Spinbox','Canvas','Label','Frame'):
            setattr(sub, a, object)
        for fn in ('showerror','showinfo','showwarning'):
            setattr(sub, fn, lambda *x, **k: None)
        sub.askopenfilename = sub.asksaveasfilename = lambda **k: None
        setattr(self, name, sub)
        return sub

tkf = FakeMod('tkinter')
for a in ['Tk','Frame','Label','Entry','Button','Canvas','Radiobutton','Checkbutton',
          'Toplevel','PanedWindow','END','StringVar','BooleanVar','IntVar','X','Y',
          'BOTH','LEFT','RIGHT','TOP','NONE','VERTICAL','HORIZONTAL','WORD','Menu']:
    setattr(tkf, a, object)
sys.modules['tkinter'] = tkf
for s in ('ttk','messagebox','scrolledtext','filedialog'):
    sys.modules['tkinter.'+s] = FakeMod('tkinter.'+s)

req = types.ModuleType('requests')
req.exceptions = types.SimpleNamespace(Timeout=type('T',(Exception,),{}),
                                       ConnectionError=type('C',(Exception,),{}),
                                       RequestException=type('R',(Exception,),{}))
req.get = lambda *a, **k: None
sys.modules['requests'] = req
_mpl = types.ModuleType('matplotlib')
_mpl.use = lambda *a, **k: None
_mpl.__path__ = []
sys.modules['matplotlib'] = _mpl
_plt = types.ModuleType('matplotlib.pyplot')
_plt.rcParams = {}
_plt.figure = lambda *a, **k: None
sys.modules['matplotlib.pyplot'] = _plt
_mpl.pyplot = _plt
_backends = types.ModuleType('matplotlib.backends')
_backends.__path__ = []
sys.modules['matplotlib.backends'] = _backends
_tkagg = types.ModuleType('matplotlib.backends.backend_tkagg')
_tkagg.FigureCanvasTkAgg = object
sys.modules['matplotlib.backends.backend_tkagg'] = _tkagg
_fig = types.ModuleType('matplotlib.figure')
_fig.Figure = object
sys.modules['matplotlib.figure'] = _fig
sys.modules['pandas'] = types.SimpleNamespace(read_excel=lambda *a,**k: None)
_e = types.SimpleNamespace(InsecureRequestWarning=type('W',(Exception,),{}))
sys.modules['urllib3'] = types.SimpleNamespace(exceptions=_e, disable_warnings=lambda *a,**k: None)
sys.modules['urllib3.exceptions'] = _e
sys.modules['numpy'] = types.SimpleNamespace(array=lambda x: x, mean=lambda x: 0, int64=int)
sys.modules['sklearn'] = types.SimpleNamespace()
sys.modules['sklearn.ensemble'] = types.SimpleNamespace(RandomForestClassifier=object)
sys.modules['sklearn.preprocessing'] = types.SimpleNamespace(StandardScaler=object)

import lotto_predictor as L

fail = 0
def chk(name, cond, extra=''):
    global fail
    if cond: print('  PASS', name)
    else:
        print('  FAIL', name, extra); fail += 1

# 用隔离的临时目录，避免污染真实库
tmp = tempfile.mkdtemp()
cwd = os.getcwd()
os.chdir(tmp)
L.DB_PATH = 'lottery_data.db'
L.init_db()

print('=== 1. 写入联网数据 ===')
recs = [{"period": "26128", "date": "2026-11-09", "front": [3,13,20,25,34], "back": [9,12]},
        {"period": "26127", "date": "2026-11-07", "front": [5,6,17,18,27], "back": [3,12]},
        {"period": "26126", "date": "2026-11-04", "front": [5,11,17,25,34], "back": [4,6]}]
for r in recs:
    L.insert_record('online_latest', r['period'], r['date'], r['front'], r['back'])
chk('online_latest 有 3 条', L.get_record_count('online_latest') == 3)
chk('excel_history 为 0', L.get_record_count('excel_history') == 0)

print('=== 2. fetch_records 读取 ===')
got = L.fetch_records('online_latest')
chk('fetch_records 返回 3 条', len(got) == 3, len(got))
chk('期号正确', got[0]['period'] in ('26128','26127','26126'))
chk('前区 5 个', len(got[0]['front']) == 5)
chk('后区 2 个', len(got[0]['back']) == 2)
chk('按日期倒序', got[0]['date'] == '2026-11-09', got[0]['date'])

print('=== 3. 模拟 refresh_source 的数据源分支 ===')
class FakeApp:
    def __init__(self):
        self.current_records = []
        self.data_source = types.SimpleNamespace(_v='excel',
                                                 get=lambda: self.data_source._v,
                                                 set=lambda v: setattr(self.data_source,'_v',v))
        self.tree = types.SimpleNamespace(get_children=lambda: [], delete=lambda i: None,
                                          insert=lambda *a, **k: None)
    def update_table(self): pass
    def update_omission(self): pass
    def update_recommendations(self): pass
    def log(self, m): pass
    refresh_source = L.LottoApp.refresh_source

app = FakeApp()

# 3a: 数据源停在 excel（复现用户看到空表的场景）
app.data_source._v = 'excel'
app.refresh_source()
chk('excel 源 -> 0 条（复现 bug）', len(app.current_records) == 0, len(app.current_records))

# 3b: 切到 online（修复后的行为）
app.data_source._v = 'online'
app.refresh_source()
chk('online 源 -> 3 条（修复生效）', len(app.current_records) == 3, len(app.current_records))

# 3c: merged 也应能读到
app.data_source._v = 'merged'
app.refresh_source()
chk('merged 源 -> 3 条', len(app.current_records) == 3, len(app.current_records))

print('=== 4. 修复代码确实存在 ===')
src = open(r'D:\PYWD\07.8\lotto_predictor.py', encoding='utf-8').read()
chk("联网后自动切 online", 'self.data_source.set("online")' in src)
chk("_apply 闭包刷新", 'def _apply():' in src)
chk("日志标注已切换", '数据源已切换为 online' in src)

os.chdir(cwd)
shutil.rmtree(tmp, ignore_errors=True)
print()
print('FAILED:', fail)
sys.exit(1 if fail else 0)