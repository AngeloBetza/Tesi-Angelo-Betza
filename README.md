# Ablation Study su ET-BERT: dove risiede il segnale per classificare il traffico cifrato?

Questo repository contiene il codice e le istruzioni per riprodurre lo studio di ablazione condotto sul modello **ET-BERT** ([Lin et al., WWW 2022](https://github.com/linwhitehat/ET-BERT)).

## Domanda di ricerca

ET-BERT classifica il traffico di rete cifrato (riconosce quale app/servizio ha generato un flusso) raggiungendo accuratezze molto elevate. La domanda di questa tesi è:

> Il modello ha bisogno di "vedere" il **payload cifrato** (TLS/HTTPS), oppure le informazioni contenute negli **header di trasporto (IP/TCP)** sono già sufficienti per identificare l'applicazione? E questa risposta è **universale**, o dipende dal dataset?

Per rispondere, confrontiamo versioni identiche di ET-BERT, addestrate **da zero** (pre-training + fine-tuning) su varianti dello stesso dataset:

| Braccio | Header IP/TCP | IP e porte | Payload TLS |
|---|---|---|---|
| **HEADER-ONLY** | visibile | azzerati | **azzerato** |
| **PAYLOAD-ONLY** | **azzerato** | azzerati | reale |
| **FULL** (baseline) | visibile | azzerati | reale |

In tutti i bracci IP e porte sono azzerati, per evitare che il modello usi scorciatoie di identificazione banali. Confrontando i bracci si isola **dove** risiede l'informazione discriminante.

## Il risultato centrale: la risposta dipende dal dataset

Abbiamo condotto lo stesso identico studio su **due dataset** con caratteristiche diverse, e i risultati sono **opposti**:

| Braccio | Cross-Platform (cifratura datata) | CipherSpectrum (TLS 1.3, cattura virtualizzata) |
|---|---|---|
| **HEADER-ONLY** | **98.13 %** | 4.59 % |
| **PAYLOAD-ONLY** | 1.38 % | **33.66 %** |
| **FULL** | 98.65 % | 25.71 % |

- Su **Cross-Platform** il segnale sta **negli header**: bastano da soli (98 %), il payload cifrato è quasi inutile.
- Su **CipherSpectrum** il segnale sta **nel payload**: payload-only eguaglia e supera il traffico completo, mentre gli header da soli collassano quasi al livello del caso (2.44 %).

**Conclusione:** l'affermazione "per classificare il traffico cifrato bastano gli header" **non è universale**. Dipende dal dataset e dal metodo di cattura. I risultati stellari della letteratura riflettono dataset in cui i metadati degli header sono molto informativi — non una capacità intrinseca del modello.

### Nota importante sulla natura del risultato

Il 33 % ottenuto da payload-only su CipherSpectrum **non significa che il modello legge il contenuto cifrato** — questo è impossibile per costruzione. Il modello sfrutta i **metadati che restano visibili nonostante la cifratura** (lunghezze dei record, pattern di trasmissione): un canale laterale noto in letteratura (traffic/website fingerprinting), non una violazione della crittografia.

---

## Risultati dettagliati

### Cross-Platform (214 app)

Fine-tuning a 50 epoche, pre-training da zero (~170k step per braccio). Metriche complete in [`RESULTS_crossplatform.md`](RESULTS_crossplatform.md).

| Braccio | Accuracy | Macro Precision | Macro Recall | Macro F1 |
|---|---|---|---|---|
| **HEADER-ONLY** | **98.13 %** | 92.29 % | 92.22 % | **91.86 %** |
| **FULL** | **98.65 %** | 93.83 % | 94.16 % | **93.60 %** |

Il modello classifica le app cifrate con il **98.1 % di accuratezza senza vedere un solo byte del payload**. Le 4 app classificate solo dal modello FULL sono quelle con pochissimi flussi di training (4-8 esempi): effetto di scarsità dati, non prova che il payload sia necessario.

### CipherSpectrum (41 domini, TLS 1.3)

Fine-tuning a 50 epoche, pre-training da zero (500k step per braccio). Metriche complete in [`RESULTS_cipherspectrum.md`](RESULTS_cipherspectrum.md).

| Braccio | Accuracy | Macro Precision | Macro Recall | Macro F1 |
|---|---|---|---|---|
| **PAYLOAD-ONLY** | **33.66 %** | 40.34 % | 33.66 % | **29.80 %** |
| **FULL** | 25.71 % | 31.00 % | 32.49 % | 28.01 % |
| **HEADER-ONLY** | 4.59 % | 0.22 % | 4.59 % | 0.43 % |

Misura diretta: sugli header di CipherSpectrum, **solo il 22 % delle posizioni-byte varia tra i domini** (il resto è costante), probabile effetto dell'ambiente di cattura virtualizzato e uniforme — questo spiega perché gli header da soli collassano.

### Osservazione dal pre-training (entrambi i dataset)

Il task Masked BURST Model (ricostruzione di byte mascherati) raggiunge alta accuratezza sugli header (strutturati e prevedibili) e bassa sul payload (crittograficamente casuale). Conferma che la cifratura rende il payload effettivamente casuale a livello di contenuto: il segnale utile, dove c'è, sta nei metadati strutturali, non nel contenuto.

---

## Come riprodurre l'esperimento

La pipeline si basa su ET-BERT ufficiale con **modifiche minime e documentate** (vedi [`PATCH_ET-BERT.md`](PATCH_ET-BERT.md)). Lo studio non ridistribuisce ET-BERT: si clona il repo originale e si applicano le patch.

### Prerequisiti
- Ubuntu Linux, Python 3.12, ambiente virtuale dedicato
- PyTorch + CUDA, GPU NVIDIA (usate 2× RTX A6000)
- `scapy`, `scikit-learn`, `xlrd`, e i requisiti di ET-BERT/UER

### Pipeline completa

```
PCAP grezzi
   │
   │  [1] ablate_pcap.py          ← ablazione con Scapy (azzera payload/header + neutralizza IP/porte)
   ▼
PCAP ablati (HEADER-ONLY / PAYLOAD-ONLY / FULL)
   │
   │  [2] vocab_process/main.py   ← costruzione corpus BURST + vocabolario (ET-BERT, con patch)
   │  [3] preprocess.py           ← corpus → dataset binario .pt per il pre-training (ET-BERT)
   ▼
   │  [4] pretrain.py             ← PRE-TRAINING DA ZERO (ET-BERT), un braccio per GPU
   ▼
Modello pre-addestrato (per ciascun braccio)
   │
   │  [5] generate_finetune_tsv.py ← genera i TSV di fine-tuning (flow-level) — codice nostro
   │  [6] remap_labels.py          ← rende contigui i label (codice nostro)
   ▼
   │  [7] run_classifier.py        ← FINE-TUNING 50 epoche (ET-BERT)
   ▼
Risultati (accuracy / F1 / confusion matrix)
```

I comandi esatti per ogni passo sono in [`PIPELINE.md`](PIPELINE.md).

---

## Contenuto del repository

| File | Descrizione |
|---|---|
| `ablate_pcap.py` | Ablazione PCAP con Scapy: azzera payload o header, neutralizza IP/porte, ricalcola checksum |
| `generate_finetune_tsv.py` | Genera i TSV di fine-tuning (flow-level) dai PCAP ablati |
| `remap_labels.py` | Rende contigui i label (0..N-1) escludendo classi con dati insufficienti |
| `RESULTS_crossplatform.md` | Risultati dettagliati sul dataset Cross-Platform |
| `RESULTS_cipherspectrum.md` | Risultati dettagliati sul dataset CipherSpectrum |
| `PATCH_ET-BERT.md` | Le modifiche esatte (riga per riga) da applicare a ET-BERT ufficiale |
| `PIPELINE.md` | Tutti i comandi, in ordine, per riprodurre l'esperimento end-to-end |
| `requirements.txt` | Dipendenze aggiuntive rispetto a ET-BERT |

## Licenza e attribuzione

ET-BERT è di Lin et al. ed è soggetto alla loro licenza. Questo repository contiene esclusivamente codice originale e istruzioni di modifica; non ridistribuisce il codice di ET-BERT.
