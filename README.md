# LMU AI Race Engineer

[English version available here](README_EN.md)

AIがリアルタイムのテレメトリを読み取り、レース無線風の指示を出してくれるツールです。  
Le Mans Ultimate + LM Studio（ローカルLLM）を組み合わせて動作します。

<!-- Add demo GIF here -->

---

## 概要

rFactor 2 共有メモリ（`rFactor2SharedMemoryMapPlugin64.dll`）から直接テレメトリを取得し、  
ローカルで動くLLM（LM Studio）に送信して、AIエンジニアの短い指示を生成します。

SimHub は不要です。LMU に同梱されているプラグインがすでに共有メモリへデータを書き出しています。

### 取得できるデータ（主なもの）

- 速度・ギア・RPM・燃料
- タイヤ摩耗 / 温度 / 空気圧 / コンパウンド（4輪）
- 前後車両とのギャップ・リーダーとのギャップ
- 残りレース時間・残りラップ数
- 天候（雨量・気温・路面温度・風速）
- 車体ダメージ・パーツ脱落・オーバーヒート警告
- ERS バッテリー残量・モーター温度
- セクタータイム・ベストラップ

### 人格

- **2種類の人格** — プロのエンジニア / かわいい女の子エンジニア「アイ」
- 日本語 / English 対応
- 完全ローカル動作（クラウド不要）

---

## 必要なもの

| ソフトウェア | 用途 |
|---|---|
| [Le Mans Ultimate](https://www.lemansultimate.com/) | レースシム本体（rF2 SharedMemory プラグイン同梱） |
| [LM Studio](https://lmstudio.ai/) | ローカルLLMサーバー |
| Python 3.9以上 | スクリプト実行 |

> **SimHub は不要です。** LMU に同梱の `rFactor2SharedMemoryMapPlugin64.dll` が共有メモリへの書き出しを担います。

---

## セットアップ

### 1. リポジトリをクローン

```bash
git clone https://github.com/akisakurap/LMU-AI.git
cd LMU-AI
```

### 2. 依存ライブラリをインストール

```bash
pip install openai
```

`mmap` と `ctypes` は Python 標準ライブラリに含まれているため、追加インストール不要です。

### 3. LMU の SharedMemory プラグインを確認

LMU をインストールした時点で `rFactor2SharedMemoryMapPlugin64.dll` は  
`<LMU>\Plugins\` フォルダに配置されています。追加作業は不要です。

### 4. LM Studio でモデルを起動

1. LM Studio でモデルをロード（例: `google/gemma-4-e2b`）
2. **Local Server** タブから **Start Server** をクリック（デフォルトポート: `1234`）

> **Tip:** 推論モデル（Thinking model）を使う場合は `max_tokens` を大きめに設定してください（デフォルト: 1500）。

### 5. 設定を編集

`race_engineer.py` の上部にある設定変数を自分の環境に合わせて変更します。

```python
LANGUAGE   = 'ja'                   # 'ja'（日本語）または 'en'（英語）
PERSONA    = 'default'              # 'default'（プロ）または 'girl'（アイちゃん）
MODEL_NAME = 'google/gemma-4-e2b'  # LM Studio でロードしているモデル名（完全一致）
```

---

## 使い方

LMU を起動してセッションに入った状態で実行します。

```bash
python race_engineer.py
```

`INTERVAL_SEC`（デフォルト 10 秒）ごとにテレメトリを読み取り、LLM へ送信します。  
停止するには `Ctrl+C` を押してください。

### 出力サンプル（default）

```
============================================================
  Race Engineer — LMU + rF2 SharedMemory + LM Studio
  Persona: default | Language: ja | Model: google/gemma-4-e2b
  LLM call: every 10s
  Press Ctrl+C to stop.
============================================================
[2026-05-06 15:23:01] Lap 12 | 245 km/h | Fuel: 42.3L | P3/20
  Gap: +1.234s / -0.876s | Leader: 8.5s
------------------------------------------------------------
[ENGINEER] タイヤ右フロントの温度が少し高めです。次のセクターでブレーキングを少し早めてください。燃料は問題ありません。
============================================================
```

### 出力サンプル（girl）

```
============================================================
[2026-05-06 15:23:01] Lap 12 | 245 km/h | Fuel: 42.3L | P3/20
  Gap: +1.234s / -0.876s | Leader: 8.5s
------------------------------------------------------------
[ENGINEER] 右フロントのタイヤ温度がちょっと高めだよ！次のコーナー、ブレーキ少し早めてみて。燃料は大丈夫、頑張って！
============================================================
```

---

## 設定リファレンス

| 変数 | デフォルト | 説明 |
|---|---|---|
| `LANGUAGE` | `'ja'` | 指示の言語。`'ja'`（日本語）または `'en'`（英語） |
| `PERSONA` | `'default'` | AIの人格。`'default'`（プロ）または `'girl'`（アイちゃん） |
| `MODEL_NAME` | `'google/gemma-4-e2b'` | LM Studioでロードするモデル名（完全一致） |
| `INTERVAL_SEC` | `10` | LLMへの問い合わせ間隔（秒） |
| `LLM_TIMEOUT` | `30` | LLM呼び出しのタイムアウト（秒） |
| `LM_STUDIO_URL` | `http://localhost:1234/v1` | LM StudioのベースURL |

---

## スクリーンショット

<!-- Add screenshot here -->

---

## ライセンス

MIT
