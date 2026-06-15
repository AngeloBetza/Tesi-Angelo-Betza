#!/usr/bin/env python3
import os, sys, glob, random, argparse, csv, binascii
import numpy as np
from sklearn.model_selection import StratifiedShuffleSplit
from scapy.all import rdpcap

random.seed(42); np.random.seed(42)

# ---- bigram_generation inline (stessa logica di dataset_generation.py) ----
def _cut(obj, sec):
    rem = len(obj) % sec
    if rem == 0:
        return [obj[i:i+sec] for i in range(0, len(obj), sec)]
    return [obj[i:i+sec+rem] for i in range(0, len(obj), sec+rem)]

def _bigram(hex_str, packet_len=128):
    chars = _cut(hex_str, 1)
    result = ''
    for i in range(len(chars)-1):
        if i+1 >= packet_len: break
        result += chars[i] + chars[i+1] + ' '
    return result
# --------------------------------------------------------------------------

def flow_feature(pcap_path, payload_len=128, payload_pac=5):
    try:
        packets = rdpcap(pcap_path)
    except Exception as e:
        return None, f"rdpcap: {e}"
    if len(packets) < 3:
        return None, f"solo {len(packets)} pacchetti"
    flow_str = ''
    for pkt in list(packets)[:payload_pac]:
        hex_s = binascii.hexlify(bytes(pkt)).decode()[28:]  # salta Ethernet (14B)
        flow_str += _bigram(hex_s, payload_len)
    s = flow_str.strip()
    return (s, None) if s else (None, "stringa vuota")

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--pcap_dir",          required=True)
    p.add_argument("--output_dir",        required=True)
    p.add_argument("--samples_per_class", type=int, default=500)
    p.add_argument("--payload_len",       type=int, default=128)
    p.add_argument("--payload_pac",       type=int, default=5)
    return p.parse_args()

def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    app_dirs = sorted([d for d in os.listdir(args.pcap_dir)
                       if os.path.isdir(os.path.join(args.pcap_dir, d))])
    print(f"Classi trovate: {len(app_dirs)}")
    with open(os.path.join(args.output_dir, "label_map.txt"), "w") as f:
        [f.write(f"{i}\t{n}\n") for i, n in enumerate(app_dirs)]

    all_feat, all_lab = [], []
    for idx, name in enumerate(app_dirs):
        pcaps = sorted(glob.glob(os.path.join(args.pcap_dir, name, "**", "*.pcap"), recursive=True))
        random.shuffle(pcaps)
        feats, errors = [], {}
        for p in pcaps:
            if len(feats) >= args.samples_per_class: break
            feat, err = flow_feature(p, args.payload_len, args.payload_pac)
            if feat:
                feats.append(feat)
            elif err:
                errors[err] = errors.get(err, 0) + 1
        if len(feats) < 3:
            print(f"  [SKIP] {name}: {len(feats)} flow validi | errori: {errors}")
            continue
        all_feat.extend(feats); all_lab.extend([idx]*len(feats))
        print(f"  [{idx:3d}] {name}: {len(feats)} flow")

    print(f"\nTotale: {len(all_feat)} flow su {len(app_dirs)} classi")
    if len(all_feat) == 0:
        print("ERRORE: nessun flow estratto. Controlla i log sopra."); return

    from collections import defaultdict
    cs = defaultdict(list)
    for f, l in zip(all_feat, all_lab): cs[l].append(f)
    Xtr, ytr, Xv, yv, Xt, yt = [], [], [], [], [], []
    for lbl, samps in sorted(cs.items()):
        random.shuffle(samps); n = len(samps)
        if n == 1:
            Xtr.append(samps[0]); ytr.append(lbl)
        elif n == 2:
            Xtr.append(samps[0]); ytr.append(lbl)
            Xv.append(samps[1]);  yv.append(lbl)
        elif n == 3:
            Xtr.append(samps[0]); ytr.append(lbl)
            Xv.append(samps[1]);  yv.append(lbl)
            Xt.append(samps[2]);  yt.append(lbl)
        else:
            nte = max(1, round(n*0.1)); nva = max(1, round(n*0.1)); ntr = n-nte-nva
            Xtr.extend(samps[:ntr]);       ytr.extend([lbl]*ntr)
            Xv.extend(samps[ntr:ntr+nva]); yv.extend([lbl]*nva)
            Xt.extend(samps[ntr+nva:]);    yt.extend([lbl]*nte)

    def write_tsv(path, F, L):
        with open(path, "w", newline="") as f:
            w = csv.writer(f, delimiter="\t")
            [w.writerow([l, feat]) for feat, l in zip(F, L)]
        print(f"  {path}  ({len(F)} righe)")

    print("Scrittura TSV...")
    write_tsv(os.path.join(args.output_dir, "train_dataset.tsv"), Xtr, ytr)
    write_tsv(os.path.join(args.output_dir, "valid_dataset.tsv"), Xv,  yv)
    write_tsv(os.path.join(args.output_dir, "test_dataset.tsv"),  Xt,  yt)
    print("Fatto.")

if __name__ == "__main__":
    main()
