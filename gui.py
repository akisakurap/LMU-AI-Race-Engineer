"""
gui.py
======
Tkinter desktop dashboard for the LMU AI Race Engineer.

Wraps race_engineer's polling loop in a background thread and shows live
telemetry + engineer radio messages in a window, with Start/Stop and
config controls that previously required CLI flags or editing
race_engineer.py directly.

Usage:
    python gui.py
"""

import queue
import tkinter as tk
from tkinter import ttk

import race_engineer as engine
from engineer_worker import EngineerWorker

POLL_INTERVAL_MS = 150   # how often the UI drains the worker's result queue
MAX_LOG_LINES    = 500   # cap so a multi-hour endurance race doesn't grow unbounded


class RaceEngineerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title('LMU AI Race Engineer')
        root.geometry('980x640')
        root.minsize(760, 480)

        self.result_queue: queue.Queue = queue.Queue()
        self.worker = EngineerWorker(self.result_queue)

        self.language_var = tk.StringVar(value=engine.LANGUAGE)
        self.persona_var  = tk.StringVar(value=engine.PERSONA)
        self.model_var    = tk.StringVar(value=engine.MODEL_NAME)
        self.url_var      = tk.StringVar(value=engine.LM_STUDIO_URL)
        self.interval_var = tk.StringVar(value=str(engine.INTERVAL_SEC))
        self.timeout_var  = tk.StringVar(value=str(engine.LLM_TIMEOUT))
        self.max_age_var = tk.StringVar(value=str(engine.MAX_DATA_AGE_SEC))
        self.tts_var      = tk.BooleanVar(value=engine.ENABLE_TTS)
        self.status_var   = tk.StringVar(value='停止中')
        self._stopping = False
        self._last_capture_at = 0

        self._config_widgets = []
        self._build_widgets()
        self._poll_queue()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_widgets(self) -> None:
        self._build_config_bar()

        body = ttk.Panedwindow(self.root, orient='horizontal')
        body.pack(fill='both', expand=True, padx=8, pady=(0, 8))

        telemetry_frame = ttk.Labelframe(body, text='テレメトリ')
        self.telemetry_text = tk.Text(telemetry_frame, wrap='none', font=('Consolas', 10),
                                       state='disabled', height=10)
        self.telemetry_text.pack(fill='both', expand=True, padx=4, pady=4)
        body.add(telemetry_frame, weight=1)

        log_frame = ttk.Labelframe(body, text='エンジニア無線ログ')
        log_scroll = ttk.Scrollbar(log_frame)
        log_scroll.pack(side='right', fill='y')
        self.log_text = tk.Text(log_frame, wrap='word', font=('Consolas', 10),
                                 state='disabled', yscrollcommand=log_scroll.set)
        self.log_text.pack(fill='both', expand=True, padx=(4, 0), pady=4)
        log_scroll.config(command=self.log_text.yview)
        self.log_text.tag_config('warning', foreground='#b45309')
        body.add(log_frame, weight=2)

        status_bar = ttk.Label(self.root, textvariable=self.status_var, anchor='w',
                                relief='sunken', padding=(6, 2))
        status_bar.pack(fill='x', side='bottom')

    def _build_config_bar(self) -> None:
        bar = ttk.Frame(self.root, padding=8)
        bar.pack(fill='x')

        def labeled(parent, text, widget_factory, width=None):
            ttk.Label(parent, text=text).pack(side='left', padx=(0, 4))
            widget = widget_factory(parent)
            if width:
                widget.config(width=width)
            widget.pack(side='left', padx=(0, 12))
            self._config_widgets.append(widget)
            return widget

        labeled(bar, '言語', lambda p: ttk.Combobox(
            p, textvariable=self.language_var, values=['ja', 'en'], state='readonly'), width=4)
        labeled(bar, 'ペルソナ', lambda p: ttk.Combobox(
            p, textvariable=self.persona_var,
            values=sorted(engine.SYSTEM_PROMPTS.keys()), state='readonly'), width=8)
        labeled(bar, 'モデル', lambda p: ttk.Entry(p, textvariable=self.model_var), width=22)
        labeled(bar, 'LM Studio URL', lambda p: ttk.Entry(p, textvariable=self.url_var), width=22)
        bar = ttk.Frame(self.root, padding=(8, 0, 8, 8))
        bar.pack(fill='x')
        labeled(bar, '間隔(秒)', lambda p: ttk.Spinbox(
            p, textvariable=self.interval_var, from_=1, to=120, increment=1), width=5)
        labeled(bar, 'タイムアウト(秒)', lambda p: ttk.Spinbox(
            p, textvariable=self.timeout_var, from_=1, to=300, increment=1), width=5)
        labeled(bar, 'データ有効期限(秒)', lambda p: ttk.Spinbox(
            p, textvariable=self.max_age_var, from_=1, to=300, increment=1), width=5)

        tts_check = ttk.Checkbutton(bar, text='音声読み上げ(TTS)', variable=self.tts_var)
        tts_check.pack(side='left', padx=(0, 12))
        self._config_widgets.append(tts_check)

        self.start_btn = ttk.Button(bar, text='Start', command=self._on_start)
        self.start_btn.pack(side='right', padx=(4, 0))
        self.stop_btn = ttk.Button(bar, text='Stop', command=self._on_stop, state='disabled')
        self.stop_btn.pack(side='right')

    # ------------------------------------------------------------------
    # Start / Stop
    # ------------------------------------------------------------------

    def _on_start(self) -> None:
        try:
            interval = engine.positive_seconds(self.interval_var.get())
            timeout = engine.positive_seconds(self.timeout_var.get())
            max_age = engine.positive_seconds(self.max_age_var.get())
        except ValueError:
            self.status_var.set('エラー: 間隔・タイムアウト・有効期限は有限の正の数で指定してください')
            return

        engine.LANGUAGE      = self.language_var.get()
        engine.PERSONA       = self.persona_var.get()
        engine.MODEL_NAME    = self.model_var.get()
        engine.LM_STUDIO_URL = self.url_var.get()
        engine.INTERVAL_SEC  = interval
        engine.LLM_TIMEOUT   = timeout
        engine.MAX_DATA_AGE_SEC = max_age
        self._stopping = False
        self._last_capture_at = 0

        self._set_config_enabled(False)
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.status_var.set('実行中 — LMU接続待機中…')

        self.worker.start(enable_tts=self.tts_var.get())

    def _on_stop(self) -> None:
        self._stopping = True
        self.stop_btn.config(state='disabled')
        self.status_var.set('停止処理中…')
        self.worker.stop()

    def _set_config_enabled(self, enabled: bool) -> None:
        state = 'readonly' if enabled else 'disabled'
        entry_state = 'normal' if enabled else 'disabled'
        for widget in self._config_widgets:
            if isinstance(widget, ttk.Combobox):
                widget.config(state=state)
            elif isinstance(widget, (ttk.Entry, ttk.Spinbox, ttk.Checkbutton)):
                widget.config(state=entry_state)

    # ------------------------------------------------------------------
    # Background -> UI updates
    # ------------------------------------------------------------------

    def _poll_queue(self) -> None:
        try:
            while True:
                item = self.result_queue.get_nowait()
                self._handle_result(item)
        except queue.Empty:
            pass
        self.root.after(POLL_INTERVAL_MS, self._poll_queue)

    def _handle_result(self, item: dict) -> None:
        kind = item.get('kind')
        if self._stopping and kind not in ('stopped',):
            return
        if kind == 'started':
            self.status_var.set('実行中 — LMU接続待機中…')
        elif kind == 'stopped':
            self._stopping = False
            self.status_var.set('停止しました')
            self.start_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
            self._set_config_enabled(True)
        elif kind == 'cycle':
            self._handle_cycle(item)
        elif kind == 'telemetry':
            data = item.get('data')
            if data:
                self._last_capture_at = data['CapturedAt']
                self._set_telemetry_text(engine.build_prompt(data, engine.LANGUAGE))
            else:
                self._set_telemetry_text('テレメトリなし — 接続待機中')

    def _handle_cycle(self, item: dict) -> None:
        ts = item.get('timestamp', '')
        data = item.get('data')

        if data is None and not item.get('error'):
            self.status_var.set(f'[{ts}] LMU未起動、またはセッション外 — 待機中…')
            return

        if data is not None and data.get('CapturedAt', 0) >= self._last_capture_at:
            self._set_telemetry_text(engine.build_prompt(data, engine.LANGUAGE))

        if item.get('ok'):
            self.status_var.set(f'[{ts}] 実行中 — 接続中')
            self._append_log(f'[{ts}] {item["message"]}\n')
        else:
            self.status_var.set(f'[{ts}] 実行中 — 警告: {item.get("error")}')
            self._append_log(f'[{ts}] [警告] {item.get("error")}\n', tag='warning')

    def _set_telemetry_text(self, text: str) -> None:
        self.telemetry_text.configure(state='normal')
        self.telemetry_text.delete('1.0', 'end')
        self.telemetry_text.insert('1.0', text)
        self.telemetry_text.configure(state='disabled')

    def _append_log(self, text: str, tag=None) -> None:
        self.log_text.configure(state='normal')
        self.log_text.insert('end', text, tag)
        line_count = int(self.log_text.index('end-1c').split('.')[0])
        if line_count > MAX_LOG_LINES:
            self.log_text.delete('1.0', f'{line_count - MAX_LOG_LINES}.0')
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

    # ------------------------------------------------------------------

    def on_close(self) -> None:
        self.worker.stop()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = RaceEngineerApp(root)
    root.protocol('WM_DELETE_WINDOW', app.on_close)
    root.mainloop()


if __name__ == '__main__':
    main()
