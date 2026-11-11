# -*- coding: utf-8 -*-
"""用 import 模拟主模块前替换掉三者，测试 TrendAnalyzer 空记录分支。"""
import sys, types, unittest

class FakeMod(types.ModuleType):
    def __getattr__(self, name):
        # 让任意 tkinter.<子模块> 都返回一个占位模块
        sub = types.ModuleType(f"faketk.{name}")
        # 提供常用成员，防止后面访问炸掉
        sub.Combobox = object; sub.Notebook = object; sub.Treeview = object
        sub.Scrollbar = object; sub.Button = object; sub.Entry = object
        sub.ScrolledText = object
        sub.showerror = lambda *a, **k: None; sub.showinfo = lambda *a, **k: None
        sub.showwarning = lambda *a, **k: None
        sub.askopenfilename = lambda **k: None; sub.asksaveasfilename = lambda **k: None
        setattr(self, name, sub)
        return sub

fake = FakeMod("faketk")
for attr in ["Tk", "Frame", "Label", "Entry", "Button", "Canvas", "Radiobutton",
             "Checkbutton", "Toplevel", "PanedWindow", "END", "StringVar",
             "BooleanVar", "X", "Y", "BOTH", "LEFT", "RIGHT", "TOP", "NONE",
             "VERTICAL", "HORIZONTAL", "WORD", "Menu"]:
    setattr(fake, attr, object)
sys.modules["tkinter"] = fake
sys.modules["tkinter.ttk"] = FakeMod("faketk.ttk")
sys.modules["tkinter.messagebox"] = FakeMod("faketk.messagebox")
sys.modules["tkinter.scrolledtext"] = FakeMod("faketk.scrolledtext")
sys.modules["tkinter.filedialog"] = FakeMod("faketk.filedialog")
matplotlib_fake = types.ModuleType("matplotlib")
matplotlib_fake.use = lambda *a, **k: None
sys.modules["matplotlib"] = matplotlib_fake
sys.modules["matplotlib.pyplot"] = types.SimpleNamespace(
    rcParams={}, figure=lambda *a, **k: types.SimpleNamespace(add_subplot=lambda *a, **k: None))
sys.modules["matplotlib.backends.backend_tkagg"] = types.SimpleNamespace(FigureCanvasTkAgg=object)
sys.modules["matplotlib.figure"] = types.SimpleNamespace(Figure=object)
sys.modules["requests"] = types.SimpleNamespace()
_exc = types.SimpleNamespace(InsecureRequestWarning=type("W",(Exception,),{}))
_urllib3 = types.SimpleNamespace(exceptions=_exc)
_urllib3.disable_warnings = lambda *a, **k: None
sys.modules["urllib3"] = _urllib3
sys.modules["urllib3.exceptions"] = _exc
sys.modules["pandas"] = types.SimpleNamespace(read_excel=lambda *a, **k: None)


def _noop_StandardScaler():
    return types.SimpleNamespace(fit_transform=lambda X, *a, **k: X,
                                 transform=lambda X, *a, **k: X)
sys.modules["numpy"] = types.SimpleNamespace(array=lambda x: x, mean=lambda x: (sum(x)/len(x) if x else 0))
sys.modules["sklearn"] = types.SimpleNamespace()
sys.modules["sklearn.ensemble"] = types.SimpleNamespace(
    RandomForestClassifier=lambda **k: types.SimpleNamespace(
        fit=lambda *a, **k2: None,
        predict_proba=lambda X: [[0.1, 0.9]],
        classes_=[0, 1]))
sys.modules["sklearn.preprocessing"] = types.SimpleNamespace(
    StandardScaler=_noop_StandardScaler)

import lotto_core, lotto_predictor

class TestTrend( unittest.TestCase ):
    def render(self, records):
        from lotto_predictor import TrendAnalyzer
        return TrendAnalyzer(records)

    def test_empty(self):
        a = self.render([])
        self.assertEqual(a.get_combined_scores()[1], 0)
        self.assertEqual(a.get_repeat_scores()[5], 0)

    def test_single_empty_front(self):
        a = self.render([ {'period':'1','date':'2020','front':[],'back':[1,2]} ])
        s = a.get_combined_scores()
        self.assertEqual(sum(s.values()), 0)

    def test_repeat_two(self):
        recs = [
            {'period':'1','date':'2020-01-02','front':[1,2,3,4,5],'back':[1,2]},
            {'period':'2','date':'2020-01-01','front':[1,2,3,6,7],'back':[3,4]},
        ]
        a = self.render(recs)
        # 最近+次近交集 {1,2,3}
        rep = a.get_repeat_scores()
        self.assertEqual(rep[1], 2)
        self.assertEqual(rep[4], 0)

if __name__ == "__main__":
    unittest.main()