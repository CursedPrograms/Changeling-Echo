"""window.py - Changeling Echo's window, in Changeling's look (customtkinter, the Atelier blue).

Steps, top to bottom: pick a voice (the built-in female or male one, or your own recordings), make or check
its speech, get the models once, train (a completion bar with the stage and the epoch), try it on a recording,
and send it to the apps that speak with it (Imago Realtime, Mosaic Mask).
"""
import os
import shutil
import threading
import time
import webbrowser
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image

from echo import dataset, models, train

HERE = os.path.dirname(os.path.abspath(__file__))
STUDIO = os.path.dirname(HERE)
GITHUB = "https://github.com/CursedPrograms/Changeling-Echo"
KOFI = "https://ko-fi.com/cursedentertainment"
PINK = "#007bb7"

BLUE, BLUE_HOVER = "#007ab7", "#005184"     # the Cursed site's blue: the important buttons, and "male"


def gender_tint(seg):
    """Colours a gender selector by what's picked: female pink, male blue, anything else the usual pink."""
    def tint(value=None):
        v = (value or seg.get() or "").lower()
        colour = PINK if ("female" in v or "woman" in v) else BLUE if ("male" in v or v == "man") else PINK
        seg.configure(selected_color=colour, selected_hover_color=colour)
    old = seg.cget("command")
    seg.configure(command=lambda v: (tint(v), old(v) if old else None))
    tint()

SOURCES = {"Female (Amy)": "female", "Male (Ryan)": "male", "My recordings": "mine"}
# where trained voices go: every app that speaks with them
APPS = [os.path.join(STUDIO, "Changeling-Imago-Realtime", "voices"),
        os.path.join(os.path.dirname(STUDIO), "Mosaic-Mask", "voices")]


def set_logo(root, here):
    ico = os.path.join(here, "logo.ico")
    if os.name == "nt" and os.path.exists(ico):
        root.after(300, lambda: root.iconbitmap(ico))


class Window:
    def __init__(self):
        self.mine = None                # the folder of your own recordings
        self.job = None
        self.state = {"busy": False, "stage": "", "fraction": None, "t0": 0.0, "message": ""}
        self.lock = threading.Lock()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme(os.path.join(HERE, "theme.json"))
        self.root = ctk.CTk()
        set_logo(self.root, HERE)
        self.root.title("Changeling Echo")
        self.root.geometry("720x860")
        self.root.minsize(560, 640)
        self._build()
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.after(100, self.watch)
        self.refresh()

    def _build(self):
        page = ctk.CTkScrollableFrame(self.root, corner_radius=12)
        page.pack(fill="both", expand=True, padx=14, pady=14)
        top = ctk.CTkFrame(page, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(8, 0))
        logo = os.path.join(HERE, "logo.png")
        if os.path.exists(logo):
            ctk.CTkLabel(top, image=ctk.CTkImage(Image.open(logo), size=(64, 64)), text="").pack(side="left", padx=(0, 12))
        titles = ctk.CTkFrame(top, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(titles, text="CHANGELING", text_color="gray55", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(titles, text="Echo", font=ctk.CTkFont(size=26, weight="bold"), text_color=PINK).pack(anchor="w")
        ctk.CTkLabel(titles, text="train the voices the Changelings speak with", text_color="gray60").pack(anchor="w")

        self.bar = ctk.CTkProgressBar(page, mode="determinate")
        self.bar.set(0)
        self.bar.pack(fill="x", padx=12, pady=(14, 2))
        self.status = ctk.CTkLabel(page, text="", text_color="gray70", wraplength=640, justify="left")
        self.status.pack(anchor="w", padx=12)

        self._step(page, "1", "The voice")
        self.source = ctk.CTkSegmentedButton(page, values=list(SOURCES), command=lambda v: self.refresh())
        self.source.set("Female (Amy)")
        self.source.pack(fill="x", padx=12, pady=4)
        gender_tint(self.source)
        row = ctk.CTkFrame(page, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row, text="Name").pack(side="left")
        self.name = ctk.CTkEntry(row, placeholder_text="echo_female")
        self.name.pack(side="left", fill="x", expand=True, padx=8)
        self.pick_btn = ctk.CTkButton(row, text="Pick recordings folder", command=self.pick_folder)
        self.pick_btn.pack(side="left")

        self._step(page, "2", "The speech")
        self.speech_note = ctk.CTkLabel(page, text="", text_color="gray60", wraplength=640, justify="left")
        self.speech_note.pack(anchor="w", padx=12)
        self.speech_btn = ctk.CTkButton(page, text="Make the speech (Piper reads 100 sentences, 3 ways)", command=self.make_speech)
        self.speech_btn.pack(fill="x", padx=12, pady=4)

        self._step(page, "3", "The models (once)")
        self.models_note = ctk.CTkLabel(page, text="", text_color="gray60", wraplength=640, justify="left")
        self.models_note.pack(anchor="w", padx=12)
        self.models_btn = ctk.CTkButton(page, text="Get the models", command=self.get_models)
        self.models_btn.pack(fill="x", padx=12, pady=4)

        self._step(page, "4", "Train")
        row = ctk.CTkFrame(page, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(4, 0))
        ctk.CTkLabel(row, text="Epochs").pack(side="left")
        self.epochs_text = ctk.CTkLabel(row, text="300", text_color="gray60")
        self.epochs_text.pack(side="right")
        self.epochs = ctk.CTkSlider(page, from_=50, to=600, number_of_steps=22,
                                    command=lambda v: self.epochs_text.configure(text=f"{int(v)}"))
        self.epochs.set(300)
        self.epochs.pack(fill="x", padx=12)
        ctk.CTkLabel(page, text="More epochs sound closer to the voice and take longer: about 300 is a good "
                     "voice (an hour or two on a 6 GB card).", text_color="gray55", wraplength=640,
                     justify="left").pack(anchor="w", padx=12)
        self.train_btn = ctk.CTkButton(page, fg_color=BLUE, hover_color=BLUE_HOVER, text="Train", height=40, font=ctk.CTkFont(size=15, weight="bold"),
                                       command=self.start_training)
        self.train_btn.pack(fill="x", padx=12, pady=6)

        self._step(page, "5", "Try it")
        self.try_btn = ctk.CTkButton(page, text="Pick a recording and hear it in this voice", command=self.try_voice)
        self.try_btn.pack(fill="x", padx=12, pady=4)

        self._step(page, "6", "Send it to the apps")
        self.voices_note = ctk.CTkLabel(page, text="", text_color="gray60", wraplength=640, justify="left")
        self.voices_note.pack(anchor="w", padx=12)
        self.send_btn = ctk.CTkButton(page, text="Copy it to Imago Realtime and Mosaic Mask", command=self.send)
        self.send_btn.pack(fill="x", padx=12, pady=4)

        links = ctk.CTkFrame(page, fg_color="transparent")
        links.pack(fill="x", padx=12, pady=(18, 2))
        for text, url in (("GitHub", GITHUB), ("Ko-fi", KOFI)):
            l = ctk.CTkLabel(links, text=text, text_color=("#005184", "#34a9e3"), cursor="hand2")
            l.pack(side="left", padx=(0, 14))
            l.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
        ctk.CTkLabel(page, text="© Cursed Entertainment 2026", text_color="gray45").pack(anchor="w", padx=12, pady=(0, 10))

    def _step(self, parent, n, text):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(18, 2))
        ctk.CTkLabel(row, text=n, width=26, height=26, corner_radius=13, fg_color=PINK, text_color="white",
                     font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(row, text=text.upper(), text_color="gray60", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")

    # ---- what's there
    @property
    def kind(self):
        return SOURCES[self.source.get()]

    def voice_name(self):
        typed = self.name.get().strip()
        return typed or ("echo_" + self.kind if self.kind != "mine" else "echo_mine")

    def speech_folder(self):
        return self.mine if self.kind == "mine" else dataset.folder(self.kind)

    def refresh(self):
        folder = self.speech_folder()
        mins = dataset.minutes(folder) if folder and os.path.isdir(folder) else 0
        self.name.configure(placeholder_text="echo_" + self.kind)
        self.pick_btn.configure(state="normal" if self.kind == "mine" else "disabled")
        self.speech_btn.configure(state="disabled" if self.kind == "mine" else "normal")
        if self.kind == "mine":
            text = (f"{mins:.1f} minutes of speech in {folder}." if folder else
                    "Pick a folder of WAV recordings: one speaker, no music, at least 10 minutes.")
        else:
            text = f"{mins:.1f} minutes of speech ready." if mins else "Not made yet (under a minute)."
        if folder and 0 < mins < 10:
            text += " That's under 10 minutes: the voice may come out rough."
        self.speech_note.configure(text=text)
        mb = models.missing_mb()
        self.models_note.configure(text="All there." if not mb else
                                   f"{mb} MB to get (HiFi-GAN, RMVPE, ContentVec). A copy already on this PC is "
                                   "used first (F:\\AIModels\\rvc, or ECHO_MODEL_DIRS).")
        self.models_btn.configure(state="disabled" if not mb else "normal")
        trained = sorted(f[:-4] for f in os.listdir(train.VOICES) if f.endswith(".pth")) if os.path.isdir(train.VOICES) else []
        self.voices_note.configure(text="Trained voices: " + (", ".join(trained) if trained else "none yet."))
        ready = bool(mins) and not mb and self.job is None
        self.train_btn.configure(state="normal" if ready else "disabled")
        has = self.voice_name() in trained
        self.try_btn.configure(state="normal" if has and self.job is None else "disabled")
        self.send_btn.configure(state="normal" if has else "disabled")

    # ---- the jobs, on their own thread
    def _run(self, work, stage):
        with self.lock:
            self.state.update(busy=True, stage=stage, fraction=None, t0=time.monotonic(), message="")
        self.job = threading.Thread(target=self._guard, args=(work,), daemon=True)
        self.job.start()
        self.refresh()

    def _guard(self, work):
        try:
            message = work()
        except Exception as e:
            message = f"Couldn't: {e}"
        with self.lock:
            self.state.update(busy=False, message=message or "")

    def _progress(self, stage, fraction):
        with self.lock:
            self.state.update(stage=stage, fraction=fraction)

    def watch(self):
        with self.lock:
            s = dict(self.state)
        if s["busy"]:
            if s["fraction"] is None:
                if self.bar.cget("mode") != "indeterminate":
                    self.bar.configure(mode="indeterminate")
                    self.bar.start()
                self.status.configure(text=s["stage"] + " ...")
            else:
                if self.bar.cget("mode") != "determinate":
                    self.bar.stop()
                    self.bar.configure(mode="determinate")
                self.bar.set(s["fraction"])
                text = f"{s['stage']}  {s['fraction']:.0%}"
                elapsed = time.monotonic() - s["t0"]
                if s["fraction"] > 0.02:
                    left = int(elapsed / s["fraction"] * (1 - s["fraction"]))
                    text += f"  about {left // 3600}h {left % 3600 // 60:02d}m left"
                self.status.configure(text=text)
        elif self.job is not None and not self.job.is_alive():
            self.job = None
            self.bar.stop()
            self.bar.configure(mode="determinate")
            self.bar.set(0 if s["message"].startswith("Couldn't") else 1)
            self.status.configure(text=s["message"])
            self.refresh()
        self.root.after(200, self.watch)

    # ---- the steps
    def pick_folder(self):
        folder = filedialog.askdirectory(title="A folder of WAV recordings of one voice")
        if folder:
            self.mine = folder
            self.refresh()

    def make_speech(self):
        kind = self.kind

        def work():
            folder, mins = dataset.make(kind, lambda d, t: self._progress("Piper is speaking", d / t))
            return f"{mins:.1f} minutes of speech in {folder}."
        self._run(work, "Piper is speaking")

    def get_models(self):
        def work():
            n = models.fetch(lambda i, t, f, name: self._progress(f"Getting {name}", (i + f) / max(t, 1)))
            return f"Models ready ({n} fetched)."
        self._run(work, "Getting the models")

    def start_training(self):
        name, folder, epochs = self.voice_name(), self.speech_folder(), int(self.epochs.get())

        def work():
            stages = train.STAGES

            def say(stage, fraction):
                self._progress(f"{stages[stage]} ({stage + 1}/4)" + (f", epoch {int((fraction or 0) * epochs)}/{epochs}" if stage == 2 else ""),
                               fraction)
            pth, index = train.train(name, folder, epochs=epochs, progress=say)
            return f"Done: {os.path.basename(pth)}" + (f" and {os.path.basename(index)}" if index else "") + " in voices/."
        self._run(work, "Starting")

    def try_voice(self):
        wav = filedialog.askopenfilename(title="A recording to hear in this voice", filetypes=[("WAV", "*.wav")])
        if not wav:
            return
        name = self.voice_name()
        out = os.path.join(train.VOICES, f"{name}_try.wav")

        def work():
            train.convert(name, wav, out)
            try:
                import winsound
                winsound.PlaySound(out, winsound.SND_FILENAME | winsound.SND_ASYNC)
            except Exception:
                pass
            return f"Playing {os.path.basename(out)} (saved in voices/)."
        self._run(work, "Speaking it in this voice")

    def send(self):
        name = self.voice_name()
        sent = []
        for folder in APPS:
            app = os.path.dirname(folder)
            if not os.path.isdir(app):
                continue
            os.makedirs(folder, exist_ok=True)
            for ext in (".pth", ".index"):
                src = os.path.join(train.VOICES, name + ext)
                if os.path.exists(src):
                    shutil.copy(src, os.path.join(folder, name + ext))
            sent.append(os.path.basename(app))
        self.status.configure(text=f"Sent {name} to " + (", ".join(sent) if sent else "no apps (none found next to Studio)."))

    def run(self):
        self.root.mainloop()
