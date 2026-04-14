# LMU AI Race Engineer

AIがリアルタイムのテレメトリを読み取り、レース無線風の指示を出してくれるツールです。  
Le Mans Ultimate + SimHub + LM Studio（ローカルLLM）を組み合わせて動作します。

<!-- Add demo GIF here -->

---

## 概要

SimHubのREST APIからテレメトリデータ（速度・タイヤ・燃料・ギャップ等）を取得し、  
ローカルで動くLLM（LM Studio）に送信して、プロのレースエンジニアのような短い指示を生成します。

- 日本語 / English 対応
- 完全ローカル動作（クラウド不要）
- SimHubが対応しているシムであれば他タイトルでも動作する可能性あり

---

## 必要なもの

| ソフトウェア | 用途 |
|---|---|
| [Le Mans Ultimate](https://www.lemansultimate.com/) | レースシム本体 |
| [SimHub](https://www.simhubdash.com/) | テレメトリ取得（REST API） |
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

### 3. SimHub の REST API を有効化

1. SimHub を起動
2. **Settings → Web server** を開く
3. **Enable web server** をオンにする（デフォルトポート: `8888`）

### 4. LM Studio でモデルを起動

1. LM Studio でモデルをロード（例: `gemma-4`）
2. **Local Server** タブから **Start Server** をクリック（デフォルトポート: `1234`）

### 5. 設定を編集

`race_engineer.py` の上部にある設定変数を自分の環境に合わせて変更します。

```python
LANGUAGE   = 'ja'       # 'ja'（日本語）または 'en'（英語）
MODEL_NAME = 'gemma-4'  # LM Studio でロードしているモデル名（完全一致）
```

---

## 使い方

```bash
python race_engineer.py
```

SimHubのデータを待ち受け、最初のポーリングが成功したあとLLMへの問い合わせが始まります。  
停止するには `Ctrl+C` を押してください。

### 出力サンプル

```
============================================================
  Race Engineer — LMU + SimHub + LM Studio
  Language: ja | Model: gemma-4
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

---

## 設定リファレンス

| 変数 | デフォルト | 説明 |
|---|---|---|
| `LANGUAGE` | `'ja'` | 指示の言語。`'ja'`（日本語）または `'en'`（英語） |
| `MODEL_NAME` | `'gemma-4'` | LM Studioでロードするモデル名（完全一致） |
| `INTERVAL_SEC` | `10` | LLMへの問い合わせ間隔（秒） |
| `POLL_SEC` | `2` | SimHubポーリング間隔（秒） |
| `LLM_TIMEOUT` | `30` | LLM呼び出しのタイムアウト（秒） |
| `SIMHUB_URL` | `http://localhost:8888/api/v5/data` | SimHub REST APIのURL |
| `LM_STUDIO_URL` | `http://localhost:1234/v1` | LM StudioのベースURL |

---

## スクリーンショット

<!-- Add screenshot here -->

---

## ライセンス

MIT
