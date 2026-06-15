#!/usr/bin/env python3
"""
Rende contigui i label dei TSV di fine-tuning (0..N-1).
Aggiunge l'intestazione label<TAB>text_a richiesta da run_classifier.py.
Uso: python3 remap_labels.py datasets/finetune_headeronly datasets/finetune_full
"""
import os, sys

def remap(directory):
    files = ["train_dataset.tsv", "valid_dataset.tsv", "test_dataset.tsv"]
    all_labels = set()
    for fn in files:
        path = os.path.join(directory, fn)
        with open(path) as f:
            lines = f.readlines()
        start = 1 if lines and lines[0].startswith("label") else 0
        for line in lines[start:]:
            if line.strip():
                all_labels.add(int(line.split("\t")[0]))
    mapping = {old: new for new, old in enumerate(sorted(all_labels))}
    n = len(mapping)
    for fn in files:
        path = os.path.join(directory, fn)
        with open(path) as f:
            lines = f.readlines()
        start = 1 if lines and lines[0].startswith("label") else 0
        rows = []
        for line in lines[start:]:
            if not line.strip():
                continue
            parts = line.rstrip("\n").split("\t", 1)
            rows.append((mapping[int(parts[0])], parts[1]))
        with open(path, "w") as f:
            f.write("label\ttext_a\n")
            for lbl, text in rows:
                f.write(f"{lbl}\t{text}\n")
    lm_path = os.path.join(directory, "label_map.txt")
    if os.path.exists(lm_path):
        old_map = {}
        with open(lm_path) as f:
            for line in f:
                if not line.strip(): continue
                idx, name = line.rstrip("\n").split("\t", 1)
                old_map[int(idx)] = name
        with open(lm_path, "w") as f:
            for old_lbl, new_lbl in sorted(mapping.items(), key=lambda x: x[1]):
                f.write(f"{new_lbl}\t{old_map.get(old_lbl,'?')}\n")
    print(f"{directory}: {n} classi (rimappate 0-{n-1})")
    return n

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 remap_labels.py DIR1 [DIR2 ...]"); sys.exit(1)
    counts = [remap(d) for d in sys.argv[1:]]
    if len(set(counts)) > 1:
        print(f"ATTENZIONE: bracci con classi diverse: {counts}")
    else:
        print(f"Classi finali: {counts[0]}")

if __name__ == "__main__":
    main()
