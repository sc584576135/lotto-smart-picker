# -*- coding: utf-8 -*-
"""test_coverage.py -- lotto_coverage 模块与覆盖率优化回归测试。"""
import sys, os, random, itertools

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lotto_coverage as cov

FAILED = []
def ok(cond, msg):
    print(('  PASS ' if cond else '  FAIL ') + msg)
    if not cond:
        FAILED.append(msg)

print('=== 1. 概率常量 ===')
ok(cov.TOTAL_COMBOS == 21425712, '总组合数 21425712')
ok(cov.WINNING_COMBOS == 1429197, '中奖组合数 1429197')
ok(abs(cov.P_SINGLE_WIN - 1429197 / 21425712) < 1e-12, '单注中奖率一致')
ok(abs(cov.P_SINGLE_WIN * 100 - 6.6705) < 0.001, '单注中奖率 ≈ 6.6705%')
ok(cov.tickets_for_target(0.90) == 34, '90% 需 34 注')
ok(cov.tickets_for_target(0.99) > cov.tickets_for_target(0.90), '目标越高注数越多')

print('=== 2. 中奖判定与官方规则一致 ===')
ok(cov.is_winning([1,2,3,4,5], [1,2], [1,2,3,4,5], [1,2]), '5+2 中奖')
ok(cov.is_winning([1,2,3,4,5], [1,2], [1,2,3,4,5], [1,3]), '5+1 中奖')
ok(cov.is_winning([1,2,3,4,5], [1,2], [1,2,3,4,5], [3,4]), '5+0 中奖')
ok(cov.is_winning([1,2,3,4,9], [1,2], [1,2,3,4,5], [3,4]), '4+0 中奖')
ok(not cov.is_winning([1,2,9,10,11], [1,2], [1,2,3,4,5], [3,4]), '2+0 不中奖')
ok(not cov.is_winning([1,9,10,11,12], [1,2], [1,2,3,4,5], [3,4]), '1+0 不中奖')
ok(cov.is_winning([9,10,11,12,13], [3,4], [1,2,3,4,5], [3,4]), '0+2 中奖')
ok(not cov.is_winning([9,10,11,12,13], [1,5], [1,2,3,4,5], [3,4]), '0+1 不中奖')

print('=== 3. 重叠代价与优化器 ===')
rng = random.Random(7)
def gen_tickets(n):
    out = []
    while len(out) < n:
        f = tuple(sorted(rng.sample(range(1, 36), 5)))
        b = tuple(sorted(rng.sample(range(1, 13), 2)))
        if (f, b) not in out:
            out.append((f, b))
    return out

cand = gen_tickets(2000)
raw = cand[:20]
opt = cov.optimize(cand, 20, seed=3)
ok(len(opt) == 20, '优化器输出 20 注')
ok(len(set((tuple(f), tuple(b)) for f, b in opt)) == 20, '优化器输出无重复')
ok(cov.total_overlap(opt) < cov.total_overlap(raw), '优化后重叠低于随机')
ok(all(isinstance(f, list) and isinstance(b, list) for f, b in opt),
   '优化器返回 list 结构（与主程序一致）')

same = [(tuple(range(1, 6)), (1, 2))] * 5
ok(cov.total_overlap(same) > cov.total_overlap(gen_tickets(5)), '完全重复的注重叠最高')

print('=== 4. 覆盖率评分合理性 ===')
one = gen_tickets(1)
ok(abs(cov.coverage_score(one) - cov.P_SINGLE_WIN) < 1e-9, '单注评分 = 单注中奖率')
ok(cov.coverage_score([]) == 0.0, '空列表评分为 0')
for n in (5, 10, 20, 34):
    t = gen_tickets(n)
    s = cov.coverage_score(t)
    # 随机选号（未优化）时评分应接近独立假设值
    ok(abs(s - cov.prob_at_least_one(n)) < 0.02,
       f'{n} 注随机评分 {s*100:.1f}% 接近独立假设 {cov.prob_at_least_one(n)*100:.1f}%')
    ok(0.0 <= s <= 0.999, f'{n} 注评分在 [0, 0.999] 区间内')

print('=== 4b. 优化后评分应高于随机 ===')
c3 = gen_tickets(1500)
rnd = c3[:20]
opt20 = cov.optimize(c3, 20, seed=5)
ok(cov.coverage_score(opt20) > cov.coverage_score(rnd) + 0.01,
   '20 注优化后评分高于随机评分')

print('=== 5. 优化确实提升实测中奖率 ===')
N_DRAWS = 4000
draws = [(tuple(sorted(rng.sample(range(1, 36), 5))), tuple(sorted(rng.sample(range(1, 13), 2))))
         for _ in range(N_DRAWS)]
def measure(tk):
    return sum(1 for d in draws
               if any(cov.is_winning(f, b, d[0], d[1]) for f, b in tk)) / len(draws)
for n in (10, 20):
    c2 = gen_tickets(1200)
    r = measure(c2[:n]); o = measure(cov.optimize(c2, n, seed=9))
    ok(o >= r - 0.03, f'{n} 注：优化后实测 {o*100:.1f}% >= 随机 {r*100:.1f}% (容差3%)')

print('=== 6. explain 输出 ===')
lines = cov.explain(34)
ok(len(lines) == 4, 'explain 返回 4 行')
ok(any('6.6705' in l for l in lines), '含单注中奖率')
ok(any('34' in l for l in lines), '含 90% 注数')

print()
if FAILED:
    print(f'FAILED: {len(FAILED)}')
    for f in FAILED:
        print('  - ' + f)
    sys.exit(1)
print('ALL COVERAGE TESTS PASSED')
