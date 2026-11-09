"""train_both.py - get the models, then train the built-in voices one after the other, female then male.

    python echo/train_both.py [epochs]

What the window does step by step, in one go, for a long unattended run. Progress lines go to the console.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from echo import dataset, models, train  # noqa: E402


def main():
    epochs = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    if models.missing():
        print(f"Getting the models ({models.missing_mb()} MB) ...", flush=True)
        last = [0.0]

        def report(i, total, fraction, name):
            if time.monotonic() - last[0] > 10 or fraction >= 1:
                last[0] = time.monotonic()
                print(f"  {name}: {fraction:.0%} ({i}/{total} done)", flush=True)
        models.fetch(report)
    for voice in ("female", "male"):
        folder = dataset.folder(voice)
        if not os.path.isdir(folder) or dataset.minutes(folder) < 5:
            print(f"Making the {voice} speech ...", flush=True)
            dataset.make(voice)
        name = f"echo_{voice}"
        print(f"Training {name}: {epochs} epochs ...", flush=True)
        t0 = time.monotonic()
        pth, index = train.train(name, folder, epochs=epochs,
                                 progress=lambda s, f: print(f"  [{train.STAGES[s]}] {'' if f is None else f'{f:.0%}'}", flush=True))
        print(f"{name}: {pth}, {index} ({(time.monotonic() - t0) / 60:.0f} min)", flush=True)


if __name__ == "__main__":
    main()
