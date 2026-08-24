# TTS Integration Design
**Date:** 2026-06-29
**Project:** LMU AI Race Engineer

## Overview

LLMの返答テキストをローカルTTSエンジンで音声読み上げする機能を追加する。
完全オフライン・低遅延を優先し、日本語はVoicevox、英語はKokoro-TTSを使う。

## Architecture

新規ファイル `tts_engine.py` を1つ追加する。`race_engineer.py` からは言語を渡すだけで
エンジン選択は `tts_engine.py` 内部で完結する。

```
race_engineer.py
  └─ tts_engine.speak(text, language)
       ├─ language='ja' → VoicevoxEngine (HTTP API, localhost:50021)
       └─ language='en' → KokoroEngine  (Python lib, kokoro)
```

## Interface

```python
# tts_engine.py が公開するのはこの1関数のみ
speak(text: str, language: str) -> None
```

`race_engineer.py` 側の変更は `engineer_loop()` に1行追加するだけ。

## Engine Details

### Voicevox (ja)
- Voicevox デスクトップアプリをバックグラウンドで起動しておく
- HTTP POST `localhost:50021/audio_query` → `/synthesis` でwavを生成
- `sounddevice` または `pyaudio` で再生
- デフォルト話者ID: 3（ずんだもん）。`VOICEVOX_SPEAKER_ID` 定数で変更可能

### Kokoro-TTS (en)
- `pip install kokoro soundfile` でインストール
- `kokoro` ライブラリを直接呼び出してwav生成 → `sounddevice` で再生
- デフォルト音声: `af_heart`。`KOKORO_VOICE` 定数で変更可能

## Data Flow

```
engineer_loop()
  1. reader.read_snapshot()        # テレメトリ取得
  2. build_prompt(data, LANGUAGE)  # プロンプト生成
  3. call_engineer(prompt)         # LLM呼び出し → answer
  4. print(answer)                 # ターミナル表示（既存）
  5. speak(answer, LANGUAGE)       # ★新規: TTS読み上げ（直列）
  6. sleep(INTERVAL_SEC)           # 次ループまで待機
```

読み上げは直列（同期）。読み上げ完了後に次のループへ進む。

## Error Handling

- Voicevox未起動 → `ConnectionError` をキャッチ、警告ログ出してスキップ
- Kokoro初期化失敗 → 起動時に警告、TTS=Noneモードで動作継続
- その他例外 → キャッチしてスキップ、ループは止まらない
- TTS失敗時もテキスト表示は維持される

## Dependencies

```
# 既存
openai

# 新規追加
kokoro          # Kokoro-TTS (en)
sounddevice     # 音声再生（共通）
soundfile       # wavデータ処理（Kokoro用）
requests        # Voicevox HTTP API（ja）
numpy           # sounddevice用
```

Voicevox本体は別途デスクトップアプリとしてインストールが必要。

## Files Changed

| ファイル | 変更内容 |
|----------|----------|
| `tts_engine.py` | 新規作成 |
| `race_engineer.py` | `speak()` 呼び出し1行追加 |
| `requirements.txt` | 依存関係追加（存在する場合） |

## Addendum (2026-08-24): 非同期再生への変更

同期読み上げ（上記「読み上げは直列」）はメインループ全体を再生時間ぶんブロックし、
実質のLLM呼び出し間隔が `INTERVAL_SEC` より大きく伸びる問題があった。

`speak_async(text, language)` を追加し、`race_engineer.py` はこちらを呼ぶように変更。
バックグラウンドのワーカースレッド1本がキュー（capacity=1）を消費して直列に再生する
（音声が重ならないようにするため）。ワーカーがまだ前の発話を再生中に新しいメッセージが
届いた場合は、キュー内の未消費メッセージを新しいものに差し替える（陳腐化した無線指示を
溜め込まず、常に最新のテレメトリに基づく指示を優先する）。

同期版 `speak()` はそのまま維持（テスト・直接利用向け）。エラー処理・フォールバック挙動は
変更なし（`speak()` 内部で例外を握りつぶす設計をそのまま流用）。
