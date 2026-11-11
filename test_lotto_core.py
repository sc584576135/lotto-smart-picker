# -*- coding: utf-8 -*-
"""核心逻辑单元测试。纯标准库，py test_lotto_core.py 直接运行。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lotto_core as core


def make_rec(front, back, period="x", date=""):
    return {"period": period, "date": date, "front": front, "back": back}


def test_calc_fushi_bets():
    # C(5,5)=1, C(2,2)=1 -> 1
    assert core.calc_fushi_bets(5, 2) == 1
    # C(6,5)=6, C(3,2)=3 -> 18
    assert core.calc_fushi_bets(6, 3) == 18
    # 强制下限
    assert core.calc_fushi_bets(3, 1) == 1  # max->5,2
    print("calc_fushi_bets OK")


def test_calc_dantuo_bets():
    # 前区: 红胆2 红拖8 -> C(8,3)=56; 后区: 蓝胆1 蓝拖3 -> C(3,1)=3 -> 168
    f = core.calc_front_bets(2, 8)
    b = core.calc_back_bets(1, 3)
    assert f == 56, f
    assert b == 3, b
    assert f * b == 168
    # 胆码>=5 -> 1
    assert core.calc_front_bets(5, 0) == 1
    # 拖码不足 -> 0
    assert core.calc_front_bets(2, 1) == 0
    assert core.calc_back_bets(0, 1) == 0
    # 负数防御：胆码归0，拖码8 >= 需5 -> C(8,5)=56
    assert core.calc_front_bets(-1, 8) == 56
    print("calc_dantuo_bets OK")


def test_parse_ratio():
    assert core.parse_ratio("3:2") == (3, 2)
    assert core.parse_ratio("3:2", 5) == (3, 2)
    assert core.parse_ratio("2:3") == (2, 3)
    assert core.parse_ratio("3:3") is None  # sum=6 != 5
    assert core.parse_ratio("a:b") is None
    assert core.parse_ratio("") is None
    print("parse_ratio OK")


def test_recommend_odd_even():
    # 全是 [1,3,5,7,9] 5奇
    recs = [make_rec([1, 3, 5, 7, 9], [1, 2]) for _ in range(10)]
    assert core.recommend_odd_even(recs) == (5, 0)
    # 空
    assert core.recommend_odd_even([]) == (3, 2)
    print("recommend_odd_even OK")


def test_recommend_zone_ratio_sum_never_exceeds_total():
    import random
    random.seed(1)
    for _ in range(2000):
        recs = []
        for _ in range(random.randint(1, 40)):
            front = sorted(random.sample(range(1, 36), 5))
            recs.append(make_rec(front, [1, 2]))
        bz = [z for z in [1, 2, 3] if random.random() < 0.3]
        r = core.recommend_zone_ratio(recs, broken_zones=bz)
        assert isinstance(r, tuple) and len(r) == 3
        assert all(x >= 0 for x in r)
        active_cnt = 3 - len(bz)
        if active_cnt > 0:
            assert sum(r) == 5, f"bz={bz} r={r} sum={sum(r)}"
        else:
            assert sum(r) == 0, f"all broken bz={bz} r={r}"
        for i in bz:
            assert r[i - 1] == 0, f"broken zone {i} not zero: {r}"
    print("recommend_zone_ratio sum-invariant OK")


def test_recommend_zone_ratio_basic():
    # 全落一区 [1..11]
    recs = [make_rec([1, 2, 3, 4, 5], [1, 2]) for _ in range(100)]
    r = core.recommend_zone_ratio(recs)
    assert r[0] == 5 and r[1] == 0 and r[2] == 0, r
    print("recommend_zone_ratio basic OK")


if __name__ == "__main__":
    for name in sorted(list(globals())):
        if name.startswith("test_") and callable(globals()[name]):
            globals()[name]()
    print("ALL CORE TESTS PASSED")