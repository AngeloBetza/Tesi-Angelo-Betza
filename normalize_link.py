#!/usr/bin/env python3
"""
Normalizzazione del link layer.

I PCAP di Cross-Platform sono in formato raw IP (linktype 101), senza header
Ethernet, mentre quelli di CipherSpectrum sono Ethernet (linktype 1).

Questo e' un problema per la pipeline di ET-BERT: sia vocab_process/main.py
(corpus di pre-training) sia data_process/dataset_generation.py (TSV di
fine-tuning) scartano i primi 38 byte di ogni pacchetto, che su Ethernet
corrispondono a header Ethernet (14) + header IP (20) + porte (4). Sui PCAP
raw IP gli stessi 38 byte cadrebbero invece dentro l'header IP e l'header TCP,
quindi i due dataset verrebbero trattati in modo diverso.

Questo script incapsula i pacchetti raw IP in un header Ethernet con MAC a
zero e lascia invariati i PCAP gia' Ethernet. Dopo la normalizzazione la
pipeline e' identica sui due dataset.

Uso:
  python3 normalize_link.py INPUT_DIR OUTPUT_DIR

Va eseguito DOPO ablate_pcap.py, sui PCAP gia' ablati.
"""
import os, argparse
from scapy.all import PcapReader, PcapWriter, Ether, IP, IPv6, Raw

ZERO = "00:00:00:00:00:00"


def to_ether(pkt):
    """Restituisce il pacchetto incapsulato in Ethernet, o None se illeggibile."""
    if isinstance(pkt, Ether):
        return pkt
    b = bytes(pkt)
    if not b:
        return None
    version = b[0] >> 4
    if version == 4:
        new = Ether(src=ZERO, dst=ZERO, type=0x0800) / IP(b)
    elif version == 6:
        new = Ether(src=ZERO, dst=ZERO, type=0x86dd) / IPv6(b)
    else:
        new = Ether(src=ZERO, dst=ZERO) / Raw(b)
    new.time = pkt.time
    return new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_dir")
    ap.add_argument("output_dir")
    args = ap.parse_args()

    n_files = n_pkts = n_skip = 0
    for root, _dirs, files in os.walk(args.input_dir):
        for fname in files:
            if not fname.lower().endswith((".pcap", ".pcapng")): continue
            rel = os.path.relpath(root, args.input_dir)
            out_dir = os.path.join(args.output_dir, rel)
            os.makedirs(out_dir, exist_ok=True)
            try:
                with PcapReader(os.path.join(root, fname)) as r, \
                     PcapWriter(os.path.join(out_dir, fname), append=False, linktype=1) as w:
                    for pkt in r:
                        p = to_ether(pkt)
                        if p is None:
                            n_skip += 1
                            continue
                        w.write(p); n_pkts += 1
                n_files += 1
            except Exception as e:
                print(f"[ERRORE] {root}/{fname}: {e}")

    print(f"File: {n_files} | Pacchetti: {n_pkts} | Scartati: {n_skip}")


if __name__ == "__main__":
    main()
