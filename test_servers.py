# -*- coding: utf-8 -*-
"""验证 load_servers 与 DataFetcher 错误暴露。纯逻辑，不联网。"""
import sys, os, types, json, tempfile

sys.path.insert(0, r'D:\PYWD\07.8')

# ---- 桩掉 GUI / 三方库，只为能 import 主模块 ----
class FakeMod(types.ModuleType):
    def __getattr__(self, name):
        sub = types.ModuleType('fake.' + name)
        sub.Combobox = sub.Notebook = sub.Treeview = sub.Scrollbar = object
        sub.Button = sub.Entry = sub.ScrolledText = object
        for fn in ('showerror', 'showinfo', 'showwarning'):
            setattr(sub, fn, lambda *a, **k: None)
        sub.askopenfilename = sub.asksaveasfilename = lambda **k: None
        setattr(self, name, sub)
        return sub

tkf = FakeMod('tkinter')
for a in ['Tk','Frame','Label','Entry','Button','Canvas','Radiobutton','Checkbutton',
          'Toplevel','PanedWindow','END','StringVar','BooleanVar','IntVar','X','Y',
          'BOTH','LEFT','RIGHT','TOP','NONE','VERTICAL','HORIZONTAL','WORD','Menu']:
    setattr(tkf, a, object)
sys.modules['tkinter'] = tkf
for sub in ('ttk','messagebox','scrolledtext','filedialog'):
    sys.modules['tkinter.' + sub] = FakeMod('tkinter.' + sub)

# ---- requests 桩：可控失败 ----
class FakeResp:
    def __init__(self, code=200, payload=None, text=''):
        self.status_code = code
        self._payload = payload or {}
        self.text = text
    def json(self): return self._payload

req = types.ModuleType('requests')
class _Timeout(Exception): pass
class _ConnErr(Exception): pass
class _ReqExc(Exception): pass
req.exceptions = types.SimpleNamespace(
    Timeout=_Timeout, ConnectionError=_ConnErr, RequestException=_ReqExc)
req.get = lambda *a, **k: FakeResp()
sys.modules['requests'] = req

mpl = types.ModuleType('matplotlib'); mpl.use = lambda *a, **k: None
sys.modules['matplotlib'] = mpl
sys.modules['matplotlib.pyplot'] = types.SimpleNamespace(rcParams={}, figure=lambda *a, **k: None)
sys.modules['matplotlib.backends.backend_tkagg'] = types.SimpleNamespace(FigureCanvasTkAgg=object)
sys.modules['matplotlib.figure'] = types.SimpleNamespace(Figure=object)
sys.modules['pandas'] = types.SimpleNamespace(read_excel=lambda *a, **k: None)
_exc = types.SimpleNamespace(InsecureRequestWarning=type('W', (Exception,), {}))
_u = types.SimpleNamespace(exceptions=_exc); _u.disable_warnings = lambda *a, **k: None
sys.modules['urllib3'] = _u; sys.modules['urllib3.exceptions'] = _exc
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

print('=== 1. load_servers 默认值 ===')
cwd = os.getcwd(); os.chdir(tempfile.mkdtemp())
try:
    s = L.load_servers()
    chk('返回列表非空', isinstance(s, list) and len(s) > 0)
    chk('含极速数据', s[0]['name'].startswith('极速'))
    chk('appkey 存在', s[0]['params']['appkey'] == L.DEFAULT_JISU_APPKEY)
    chk('自动生成 json 模板', os.path.exists(L.SERVER_CONFIG_FILE))

    print('=== 2. load_servers 读自定义 json ===')
    custom = [{"name": "我的接口", "url": "https://x/api", "params": {"appkey": "MYKEY"},
               "method": "GET", "type": "jisuapi"}]
    with open(L.SERVER_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(custom, f, ensure_ascii=False)
    s2 = L.load_servers()
    chk('读到自定义配置', s2[0]['name'] == '我的接口')
    chk('appkey 已覆盖', s2[0]['params']['appkey'] == 'MYKEY')

    print('=== 3. 坏 json 回退默认 ===')
    with open(L.SERVER_CONFIG_FILE, 'w', encoding='utf-8') as f:
        f.write('{bad json')
    s3 = L.load_servers()
    chk('坏文件仍返回默认', s3[0]['name'].startswith('极速'))

    print('=== 4. fetch_from_server 错误暴露 ===')
    srv = L.DEFAULT_SERVERS[0]
    # 4a HTTP 500
    req.get = lambda *a, **k: FakeResp(500, text='server error')
    r = L.DataFetcher.fetch_from_server(srv, 20)
    chk('HTTP500 返回None', r is None)
    chk('HTTP500 记录原因', 'HTTP 500' in L.DataFetcher.last_error, L.DataFetcher.last_error)

    # 4b 超时
    def _to(*a, **k): raise _Timeout('timed out')
    req.get = _to
    r = L.DataFetcher.fetch_from_server(srv, 20)
    chk('超时返回None', r is None)
    chk('超时原因含"超时"', '超时' in L.DataFetcher.last_error, L.DataFetcher.last_error)

    # 4c 连接失败
    def _ce(*a, **k): raise _ConnErr('dns fail')
    req.get = _ce
    r = L.DataFetcher.fetch_from_server(srv, 20)
    chk('连接失败原因含"连接"', '连接' in L.DataFetcher.last_error, L.DataFetcher.last_error)

    # 4d 正常
    req.get = lambda *a, **k: FakeResp(200, {"status": 0, "result": {"list": [
        {"issueno": "24001", "opendate": "2024-01-01",
         "number": "1 2 3 4 5", "refernumber": "6 7"}]}})
    r = L.DataFetcher.fetch_from_server(srv, 20)
    chk('正常返回dict', isinstance(r, dict))
    chk('正常无错误', L.DataFetcher.last_error == '')

    print('=== 5. parse_response 业务错误 ===')
    bad = {"status": 201, "msg": "appkey错误"}
    recs = L.DataFetcher.parse_response(bad, 'jisuapi')
    chk('业务错误返回空', recs == [])
    chk('业务错误原因含 status', 'status=201' in L.DataFetcher.last_error, L.DataFetcher.last_error)

    good = {"status": 0, "result": {"list": [
        {"issueno": "24001", "opendate": "2024-01-01", "number": "1 2 3 4 5", "refernumber": "6 7"},
        {"issueno": "24002", "opendate": "2024-01-02", "number": "10 11 12 13 14", "refernumber": "3 9"}]}}
    recs = L.DataFetcher.parse_response(good, 'jisuapi')
    chk('正常解析2条', len(recs) == 2)
    chk('前区5个', len(recs[0]['front']) == 5)
    chk('后区2个', len(recs[0]['back']) == 2)
    chk('期号正确', recs[0]['period'] == '24001')
finally:
    os.chdir(cwd)

print()
print('FAILED:', fail)
sys.exit(1 if fail else 0)