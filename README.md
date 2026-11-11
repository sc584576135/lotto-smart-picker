# 大乐透智能选号（Lotto Smart Picker）

Windows 桌面版（tkinter）+ 华为/Android 手机 APP（WebView）一体的大乐透选号工具。
核心是**覆盖率优化引擎**：同等注数下最小化注间重叠，提升「至少中一注」的概率。

> 诚实声明：任何选号策略都无法改变单注 6.6705% 的中奖率和约 50% 的返奖率。
> 本工具的"覆盖率"指**一组 N 注号码覆盖开奖结果（至少中一注）的概率**，
> 由蒙特卡洛模拟实测（见 `app/measure_js.js`）与超几何精确公式（`app/verify_exact.js`）交叉验证。

## 双端对比

| 能力 | 桌面版 (`lotto_predictor.py`) | 手机 APP (`android/lotto.apk`) |
|---|---|---|
| 普通 / 复式 / 胆拖三模式 | ✅ | ✅ |
| 和值 / 跨度 / 奇数 / 断区 / 区间比 / 杀号 | ✅ | ✅ |
| 遗漏分层加权 / 对码互斥 / 覆盖率优化 | ✅ | ✅ |
| 1~50 注档位（含 34 注 ≈ 92.6%） | ✅ | ✅ |
| 开奖数据 | 极速数据 API + Excel 导入 | **体彩官方接口**（免 key） |
| 选号记录保存 | txt 导出 | localStorage + **JSON 导出** |
| 中奖核对 | 反馈对比 tab | 核对页（13 条奖级规则） |
| AI 辅助选号 | ✅（lotto_ai.py） | ✅（lotto-ai.js，预设 5 家服务商） |
| 登录 | 有（桌面版） | 无（APP 版已取消） |

## 覆盖率实测（JS 引擎，40000 次蒙特卡洛 × 5 重复）

| 注数 | 金额 | 随机选号 | 优化后 | 独立理论上限 |
|---|---|---|---|---|
| 5 | 10 元 | 29.5% | **31.9%** | 29.2% |
| 10 | 20 元 | 49.8% | **55.3%** | 49.9% |
| 17 | 34 元 | 68.8% | **74.6%** | 69.1% |
| 20 | 40 元 | 74.8% | **78.7%** | 74.9% |
| 34 | 68 元 | 91.3% | **92.6%** | 90.4% |
| 50 | 100 元 | 96.9% | **97.5%** | 96.8% |

> 覆盖率优化靠**负相关选号**：让每注尽量"不重叠"，并集覆盖就会超过
> `1-(1-p)^n` 的独立假设上限（见 `lotto_coverage.py` 的贪心优化器）。
> 断区/杀号等过滤条件会改变号码池，实际覆盖以结果区标签为准（实测/模拟/精确三口径）。

## 目录结构

```
├── lotto_predictor.py      # 桌面版主程序（GUI + 业务逻辑，约 2000 行）
├── lotto_core.py           # 纯逻辑模块（注数/比例计算）
├── lotto_ai.py             # 免费大模型接入（SiliconFlow/DeepSeek/GLM/百炼/OpenRouter）
├── lotto_coverage.py       # 覆盖率优化引擎（Python 版）
├── test_*.py               # 8 个测试套件（run_tests.bat 一键全跑）
├── app/                    # 手机 APP 前端（WebView 加载）
│   ├── index.html          # 五页导航：选号/开奖/记录/核对/AI
│   ├── lotto-core.js       # 核心引擎（奖级/概率/优化器，JS 版）
│   ├── lotto-rules.js      # 生成规则（遗漏分层/对码互斥/三模式）
│   ├── lotto-data.js       # 数据层（官方接口/本地存储/导出/核对）
│   ├── lotto-ai.js         # AI 接入（JS 版，对应 lotto_ai.py）
│   ├── measure_js.js       # 覆盖率蒙特卡洛实测脚本
│   └── verify_exact.js     # 超几何精确公式校验脚本
├── android/
│   ├── build_apk.ps1       # 手工构建链（aapt2→javac→d8→zipalign→apksigner）
│   ├── AndroidManifest.xml # 包名 com.yg.lotto, minSdk 21 / targetSdk 29
│   ├── src/com/yg/lotto/   # MainActivity + NetBridge（网络/文件桥）
│   ├── res/drawable/       # 图标（多分辨率）
│   ├── assets/             # 与 app/ 同步的前端资源
│   └── lotto.apk           # 已签名 APK（keystore 不入库）
└── build_win7.spec         # PyInstaller 打包配置（Win7 兼容：Python 3.8 + UPX off）
```

## 快速开始

### 桌面版

```bat
pip install requests pandas numpy matplotlib scikit-learn
python lotto_predictor.py
```

> Windows 7 打包需 Python 3.8 + PyInstaller 4.10，见 `build_win7.spec` 注释。

### 手机 APP

直接安装 `android/lotto.apk`（已签名，华为 HarmonyOS 2.0 / Android 5+ 通用）。
或改完 `app/` 前端后重建：

```powershell
Copy-Item 'app\index.html','app\app.css','app\app.js','app\lotto-core.js','app\lotto-rules.js','app\lotto-data.js','app\lotto-ai.js' 'android\assets\' -Force
powershell -ExecutionPolicy Bypass -File 'android\build_apk.ps1'
```

构建链依赖 JDK 17 与 Android SDK（`build-tools 29.0.3` / `platforms/android-29`）。
注意：本仓库不含签名私钥（`keystore.jks` 已 gitignore），克隆后需自行生成：

```bat
keytool -genkeypair -keystore android\keystore.jks -alias lotto -keyalg RSA -keysize 2048 -validity 10950 -storepass lotto2026 -keypass lotto2026 -dname "CN=YG, OU=Lotto, O=YG, L=CN, C=CN"
```

## 数据源

- 手机 APP：**体彩官方接口** `https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry?gameNo=85`，免 key 免登录。
- 桌面版：极速数据 API（`api.jisuapi.com`，内置免费 key，可在 `lottery_servers.json` 替换）+ Excel 导入。

## 中奖核对规则（与官方一致，13 条）

| 命中 | 奖级 | 奖金 | | 命中 | 奖级 | 奖金 |
|---|---|---|---|---|---|---|
| 5+2 | 一等奖 | 浮动 | | 4+0 | 五等奖 | 100 元 |
| 5+1 | 二等奖 | 浮动 | | 3+1 | 六等奖 | 15 元 |
| 5+0 | 三等奖 | 10000 元 | | 2+2 | 六等奖 | 15 元 |
| 4+2 | 四等奖 | 3000 元 | | 3+0 | 七等奖 | 5 元 |
| 3+2 | 四等奖 | 200 元 | | 2+1 | 七等奖 | 5 元 |
| 4+1 | 五等奖 | 300 元 | | 1+2 / 0+2 | 七等奖 | 5 元 |

## 测试

```bat
run_tests.bat          :: 桌面版 8 套测试
node app\measure_js.js :: 覆盖率蒙特卡洛实测
node app\verify_exact.js :: 精确公式校验（全包=100%，单注=6.6705%）
```
