# Ablation Study su ET-BERT: gli header di rete bastano per classificare il traffico cifrato?

Questo repository contiene il codice e le istruzioni per riprodurre lo studio di ablazione condotto sul modello **ET-BERT** ([Lin et al., WWW 2022](https://github.com/linwhitehat/ET-BERT)) per la tesi di laurea di Angelo Betza.

## Domanda di ricerca

ET-BERT classifica il traffico di rete cifrato riconoscendo quale app ha generato un flusso. La domanda di questa tesi è:

> Il modello ha bisogno di "vedere" il **payload cifrato** (TLS/HTTPS), oppure le informazioni contenute negli **header di trasporto (IP/TCP)** sono già sufficienti per identificare l'applicazione?

## Disegno sperimentale

Tre versioni identiche di ET-BERT, addestrate **da zero** (pre-training + fine-tuning), che differiscono solo per cosa vedono:

| Braccio | Header IP/TCP | IP e porte | Payload TLS |
|---|---|---|---|
| **FULL** (baseline) | reale | azzerati | reale |
| **HEADER-ONLY** | reale | azzerati | azzerato |
| **PAYLOAD-ONLY** | azzerato | azzerati | reale |

IP e porte sono azzerati in tutti i bracci per evitare che il modello classifichi tramite una banale corrispondenza IP→app invece che tramite pattern strutturali.

## Risultati principali

Dataset: **Cross-Platform** (214 app), fine-tuning 50 epoche, pre-training da zero per ogni braccio. Dettagli completi in [`RESULTS.md`](RESULTS.md).

| Braccio | Accuracy | Macro F1 |
|---|---|---|
| **FULL** (baseline) | 98.65% | 93.60% |
| **HEADER-ONLY** | 98.13% | 91.86% |
| **PAYLOAD-ONLY** | **1.38%** | **0.01%** |

**ET-BERT non sta "entrando" nel traffico cifrato.** Con solo gli header raggiunge il 98.1% di accuratezza (F1 91.9%), mentre con solo il payload cifrato crolla all'1.4% — praticamente il caso casuale su 214 classi (1/214 = 0.47%). Il payload TLS è crittograficamente casuale e non porta informazione classificabile.

**Dove il payload fa la differenza.** Le 4 app classificate dal FULL ma non dall'HEADER-ONLY hanno tutte 4-8 flussi di training: è un effetto di scarsità di dati, non una prova che il payload sia informativamente necessario.

### Osservazione dal pre-training

Durante il pre-training, il task Masked BURST Model raggiunge:
- **97-98%** sul braccio HEADER-ONLY (header strutturati e prevedibili)
- **3-5%** sul braccio FULL (payload TLS crittograficamente casuale; loss ≈ 10, vicino al massimo teorico ln(65536) ≈ 11.09)
- **0.3-1.3%** sul braccio PAYLOAD-ONLY (payload TLS casuale + header azzerati; loss ≈ 10.8)

---

## Come riprodurre l'esperimento

La pipeline si basa su ET-BERT ufficiale con **modifiche minime e documentate** (vedi [`PATCH_ET-BERT.md`](PATCH_ET-BERT.md)). Lo studio non ridistribuisce ET-BERT: si clona il repo originale e si applicano le patch.

### Prerequisiti
- Ubuntu Linux, Python 3.12, ambiente virtuale dedicato
- PyTorch + CUDA, GPU NVIDIA (usate 2× RTX A6000)
- `scapy`, `scikit-learn`, `xlrd`, e i requisiti di ET-BERT/UER

### Pipeline completa PCAP grezzi
│
│  [1] ablate_pcap.py           ← ablazione con Scapy (3 modalità: header-only, full, payload-only)
▼
PCAP ablati (tre varianti)
│
│  [2] vocab_process/main.py    ← corpus BURST + vocabolario (ET-BERT, con patch)
│  [3] preprocess.py            ← corpus → dataset binario .pt per il pre-training
▼
│  [4] pretrain.py              ← PRE-TRAINING DA ZERO, un braccio per GPU
▼
Modello pre-addestrato
│
│  [5] generate_finetune_tsv.py ← TSV di fine-tuning (flow-level)
│  [6] remap_labels.py          ← label contigui 0..N-1
▼
│  [7] run_classifier.py        ← FINE-TUNING 50 epoche (ET-BERT)
▼
Risultati (accuracy / F1 / confusion matrix)
I comandi esatti sono in [`PIPELINE.md`](PIPELINE.md).

---

## Risposta alle criticità metodologiche

Questo studio è una riprogettazione rigorosa di un tentativo iniziale che presentava errori metodologici. Le correzioni:

1. **Trasformazione PCAP→TSV esplicita.** L'intera catena parte dai PCAP grezzi ed è documentata e versionata.
2. **Byte inclusi noti e controllati.** Dopo l'ablazione i pacchetti contengono header IP+TCP (con indirizzi e porte azzerati) e payload azzerato o reale a seconda del braccio. Vedi `ablate_pcap.py`.
3. **Scapy effettivamente utilizzato** per l'ablazione (`ablate_pcap.py`).
4. **Niente taglio a lunghezza fissa.** Il vecchio approccio tagliava 104 byte fissi: scorretto perché gli header hanno lunghezza variabile. Ora Scapy separa dinamicamente header e payload.
5. **Pre-training rifatto da zero** su ciascun dataset modificato, prima del fine-tuning. Non si usano corpus/vocab/pesi forniti dagli autori: il modello, durante il pre-training, vede gli stessi dati che vedrà nel fine-tuning, eliminando il problema out-of-distribution.

---

## Contenuto del repository

| File | Descrizione |
|---|---|
| `ablate_pcap.py` | Ablazione PCAP con Scapy: 3 modalità (`--keep-payload`, `--payload-only`, default header-only) |
| `generate_finetune_tsv.py` | Genera i TSV di fine-tuning (flow-level) dai PCAP ablati |
| `remap_labels.py` | Rende contigui i label (0..N-1) |
| `PATCH_ET-BERT.md` | Le modifiche esatte (riga per riga) da applicare a ET-BERT ufficiale |
| `PIPELINE.md` | Tutti i comandi, in ordine, per riprodurre l'esperimento end-to-end |
| `RESULTS.md` | Risultati completi con analisi per tutti e tre i bracci |
| `requirements.txt` | Dipendenze aggiuntive rispetto a ET-BERT |

## Licenza e attribuzione

ET-BERT è di Lin et al. ed è soggetto alla loro licenza. Questo repository contiene esclusivamente codice originale e istruzioni di modifica; non ridistribuisce il codice di ET-BERT.
