#!/usr/bin/env python3
import os, argparse
from scapy.all import PcapReader, PcapWriter, Raw, Ether, IP, IPv6, TCP, UDP

def neutralize_identifiers(pkt):
    if Ether in pkt:
        pkt[Ether].src = "00:00:00:00:00:00"
        pkt[Ether].dst = "00:00:00:00:00:00"
    if IP in pkt:
        pkt[IP].src = "0.0.0.0"
        pkt[IP].dst = "0.0.0.0"
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
    l4 = pkt.getlayer(TCP) or pkt.getlayer(UDP)
    if l4 is not None and l4.payload:
        n = len(bytes(l4.payload))
        if n > 0:
            l4.remove_payload()
            l4.add_payload(Raw(load=b"\x00" * n))

def process_packet(pkt, zero_payload):
    neutralize_identifiers(pkt)
    if zero_payload:
        zero_l4_payload(pkt)
    return pkt.__class__(bytes(pkt))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_dir")
    ap.add_argument("output_dir")
    ap.add_argument("--keep-payload", action="store_true")
    args = ap.parse_args()
    zero_payload = not args.keep_payload
    n_files = n_pkts = n_passthrough = 0
    for root, _dirs, files in os.walk(args.input_dir):
        for fname in files:
            if not fname.lower().endswith((".pcap", ".pcapng")): continue
            in_path = os.path.join(root, fname)
            rel = os.path.relpath(root, args.input_dir)
            out_dir = os.path.join(args.output_dir, rel)
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, fname)
            try:
                with PcapReader(in_path) as reader, PcapWriter(out_path, append=False) as writer:
                    for pkt in reader:
                        try:
                            writer.write(process_packet(pkt, zero_payload))
                            n_pkts += 1
                        except Exception:
                            writer.write(pkt); n_passthrough += 1
                n_files += 1
            except Exception as e:
                print(f"[ERRORE] {in_path}: {e}")
    mode = "FULL (payload mantenuto)" if args.keep_payload else "HEADER-ONLY (payload azzerato)"
    print(f"Modalita': {mode}")
    print(f"File: {n_files} | Modificati: {n_pkts} | Intatti: {n_passthrough}")

if __name__ == "__main__":
    main()
