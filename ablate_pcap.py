#!/usr/bin/env python3
"""
Ablazione dei PCAP per lo studio di ablazione su ET-BERT.

Tre modalita', una per braccio sperimentale:

  FULL          (--keep-payload)  header reali, payload reale
  HEADER-ONLY   (default)         header reali, payload azzerato
  PAYLOAD-ONLY  (--payload-only)  header azzerati, payload reale

In tutte le modalita' vengono neutralizzati MAC, indirizzi IP e porte, in modo
che il modello non possa classificare riconoscendo il server con cui l'app
comunica (shortcut learning).

Nella modalita' PAYLOAD-ONLY vengono azzerati anche il checksum TCP e il campo
dataofs (lunghezza dell'header TCP), che altrimenti resterebbero informativi.
Le lunghezze dei pacchetti non vengono mai modificate.

Uso:
  python3 ablate_pcap.py INPUT_DIR OUTPUT_DIR [--keep-payload | --payload-only]

La struttura di cartelle (una per classe) viene preservata.
"""
import os, argparse
from scapy.all import PcapReader, PcapWriter, Raw, Ether, IP, IPv6, TCP, UDP


def neutralize_identifiers(pkt):
    """Azzera MAC, IP e porte. Applicata a FULL e HEADER-ONLY."""
    if Ether in pkt:
        pkt[Ether].src = "00:00:00:00:00:00"
        pkt[Ether].dst = "00:00:00:00:00:00"
    if IP in pkt:
        pkt[IP].src = "0.0.0.0"; pkt[IP].dst = "0.0.0.0"
        if pkt[IP].chksum is not None: del pkt[IP].chksum
    if IPv6 in pkt:
        pkt[IPv6].src = "::"; pkt[IPv6].dst = "::"
    if TCP in pkt:
        pkt[TCP].sport = 0; pkt[TCP].dport = 0
        if pkt[TCP].chksum is not None: del pkt[TCP].chksum
    elif UDP in pkt:
        pkt[UDP].sport = 0; pkt[UDP].dport = 0
        if pkt[UDP].chksum is not None: del pkt[UDP].chksum


def zero_l4_payload(pkt):
    """Sostituisce il payload applicativo con zeri, mantenendone la lunghezza."""
    l4 = pkt.getlayer(TCP) or pkt.getlayer(UDP)
    if l4 is not None and l4.payload:
        n = len(bytes(l4.payload))
        if n > 0:
            l4.remove_payload()
            l4.add_payload(Raw(load=b"\x00" * n))


def zero_all_headers(pkt):
    """Azzera i campi degli header IP e TCP/UDP, lasciando intatto il payload.

    Rispetto alla prima versione, azzera anche TCP.chksum e TCP.dataofs:
    il checksum dipende dal contenuto e la lunghezza dell'header e' a sua volta
    informativa, quindi entrambi andavano azzerati e non ricalcolati.
    """
    if IP in pkt:
        pkt[IP].ttl = 0; pkt[IP].id = 0; pkt[IP].tos = 0
        pkt[IP].flags = 0; pkt[IP].frag = 0
        pkt[IP].src = "0.0.0.0"; pkt[IP].dst = "0.0.0.0"
        if pkt[IP].chksum is not None: del pkt[IP].chksum
    if IPv6 in pkt:
        pkt[IPv6].src = "::"; pkt[IPv6].dst = "::"
        pkt[IPv6].tc = 0; pkt[IPv6].fl = 0; pkt[IPv6].hlim = 0
    if TCP in pkt:
        pkt[TCP].sport = 0; pkt[TCP].dport = 0
        pkt[TCP].seq = 0; pkt[TCP].ack = 0
        pkt[TCP].flags = 0; pkt[TCP].window = 0
        pkt[TCP].options = []; pkt[TCP].urgptr = 0
        pkt[TCP].dataofs = 0
        pkt[TCP].chksum = 0
    elif UDP in pkt:
        pkt[UDP].sport = 0; pkt[UDP].dport = 0
        if pkt[UDP].chksum is not None: del pkt[UDP].chksum


def process_packet(pkt, mode):
    if mode == "header_only":
        neutralize_identifiers(pkt)
        zero_l4_payload(pkt)
    elif mode == "payload_only":
        zero_all_headers(pkt)
    else:
        neutralize_identifiers(pkt)
    return pkt.__class__(bytes(pkt))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_dir")
    ap.add_argument("output_dir")
    ap.add_argument("--keep-payload", action="store_true",
                    help="modalita' FULL: mantiene il payload")
    ap.add_argument("--payload-only", action="store_true",
                    help="modalita' PAYLOAD-ONLY: azzera gli header")
    args = ap.parse_args()

    if args.payload_only:
        mode = "payload_only"
    elif args.keep_payload:
        mode = "full"
    else:
        mode = "header_only"

    n_files = n_pkts = n_pass = 0
    for root, _dirs, files in os.walk(args.input_dir):
        for fname in files:
            if not fname.lower().endswith((".pcap", ".pcapng")): continue
            in_path = os.path.join(root, fname)
            rel = os.path.relpath(root, args.input_dir)
            out_dir = os.path.join(args.output_dir, rel)
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, fname)
            try:
                with PcapReader(in_path) as r, PcapWriter(out_path, append=False) as w:
                    for pkt in r:
                        try:
                            w.write(process_packet(pkt, mode)); n_pkts += 1
                        except Exception:
                            w.write(pkt); n_pass += 1
                n_files += 1
            except Exception as e:
                print(f"[ERRORE] {in_path}: {e}")

    labels = {"header_only": "HEADER-ONLY", "full": "FULL", "payload_only": "PAYLOAD-ONLY"}
    print(f"Modalita: {labels[mode]}")
    print(f"File: {n_files} | Modificati: {n_pkts} | Intatti: {n_pass}")


if __name__ == "__main__":
    main()
