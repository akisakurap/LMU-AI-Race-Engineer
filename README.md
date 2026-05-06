# LMU AI Race Engineer

AIがリアルタイムのテレメトリを読み取り、レース無線風の指示を出してくれるツールです。  
Le Mans Ultimate + SimHub + LM Studio（ローカルLLM）を組み合わせて動作します。

<!-- Add demo GIF here -->

---

## 概要

SimHubのREST APIからテレメトリデータ（速度・タイヤ・燃料・ギャップ等）を取得し、  
ローカルで動くLLM（LM Studio）に送信して、AIエンジニアの短い指示を生成します。

- **2種類の人格** — プロのエンジニア / かわいい女の子エンジニア「アイ」
- 日本語 / English 対応
- 完全ローカル動作（クラウド不要）
- SimHubが対応しているシムであれば他タイトルでも動作する可能性あり

---

## 必要なもの

| ソフトウェア | 用途 |
|---|---|
| [Le Mans Ultimate](https://www.lemansultimate.com/) | レースシム本体 |
| [SimHub](https://www.simhubdash.com/) v9以上 | テレメトリ取得（REST API） |
| [LM Studio](https://lmstudio.ai/) | ローカルLLMサーバー |
| Python 3.9以上 | スクリプト実行 |

---

## セットアップ

### 1. リポジトリをクローン

```bash
git clone https://github.com/akisakurap/LMU-AI.git
cd LMU-AI
```

### 2. 依存ライブラリをインストール

```bash
pip install openai requests
```

### 3. SimHub の Web サーバーを有効化

1. SimHub を起動
2. **Settings → General** を開く
3. **Web server** が有効になっていることを確認する（デフォルトポート: `8888`）

> **Note:** SimHub v9系では REST API エンドポイントが `/api/getgamedata` に変わっています。

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

```bash
python race_engineer.py
```

SimHubのデータを待ち受け、最初のポーリングが成功したあとLLMへの問い合わせが始まります。  
停止するには `Ctrl+C` を押してください。

### 出力サンプル（default）

```
============================================================
  Race Engineer — LMU + SimHub + LM Studio
  Persona: default | Language: ja | Model: google/gemma-4-e2b
  SimHub poll: every 2s | LLM call: every 10s
  Press Ctrl+C to stop.
============================================================
[INFO] Waiting for first SimHub data...
============================================================
[2026-04-14 15:23:01] Lap 12 | 245 km/h | Fuel: 42.3L
------------------------------------------------------------
[ENGINEER] タイヤ右フロントの温度が少し高めです。次のセクターでブレーキングを少し早めてください。燃料は問題ありません。
============================================================
```

### 出力サンプル（girl）

```
============================================================
[2026-04-14 15:23:01] Lap 12 | 245 km/h | Fuel: 42.3L
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
| `POLL_SEC` | `2` | SimHubポーリング間隔（秒） |
| `LLM_TIMEOUT` | `30` | LLM呼び出しのタイムアウト（秒） |
| `SIMHUB_URL` | `http://localhost:8888/api/getgamedata` | SimHub REST APIのURL |
| `LM_STUDIO_URL` | `http://localhost:1234/v1` | LM StudioのベースURL |

---

## スクリーンショット

<!-- Add screenshot here -->

---

## ライセンス

MIT
