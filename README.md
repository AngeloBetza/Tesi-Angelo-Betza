# Ablation Study su ET-BERT: gli header di rete bastano per classificare il traffico cifrato?

Questo repository contiene il codice e le istruzioni per riprodurre lo studio di ablazione condotto sul modello **ET-BERT** ([Lin et al., WWW 2022](https://github.com/linwhitehat/ET-BERT)) per la tesi di laurea di Angelo Betza.

## Domanda di ricerca

ET-BERT classifica il traffico di rete cifrato (riconosce quale app ha generato un flusso) raggiungendo accuratezze molto elevate. La domanda di questa tesi è:

> Il modello ha bisogno di "vedere" il **payload cifrato** (TLS/HTTPS), oppure le informazioni contenute negli **header di trasporto (IP/TCP)** sono già sufficienti per identificare l'applicazione?

Per rispondere, confrontiamo due versioni identiche di ET-BERT, addestrate **da zero** (pre-training + fine-tuning) su due varianti dello stesso dataset:

| Braccio | Header IP/TCP | IP e porte | Payload TLS |
|---|---|---|---|
| **HEADER-ONLY** (sperimentale) | visibile | azzerati | **azzerato** |
| **FULL** (baseline) | visibile | azzerati | reale |

L'unica differenza tra i due bracci è il payload. Se i due bracci ottengono accuratezze simili, il payload cifrato è irrilevante per la classificazione e l'informazione discriminante risiede negli header.

## Risultati principali

Dataset: **Cross-Platform** (214 app, dopo esclusione di 3 app con < 3 flussi validi), fine-tuning a 50 epoche, pre-training da zero (~170k step per braccio).

| Braccio | Accuracy (test set) |
|---|---|
| **HEADER-ONLY** | **98.62 %** (3583/3633) |
| **FULL** | **98.90 %** (3593/3633) |

La differenza è di **10 campioni su 3633 (0.28 punti percentuali)**: il modello classifica le app cifrate con il 98.6 % di accuratezza **senza vedere un solo byte del payload**. L'informazione discriminante è nella struttura degli header (dimensioni pacchetti, flag TCP, window size, TTL, pattern seq/ack), non nel contenuto cifrato.

### Osservazione dal pre-training

Durante il pre-training, il task Masked BURST Model (ricostruzione di byte mascherati) raggiunge:
- **97-98 %** di accuratezza sul braccio HEADER-ONLY (gli header sono strutturati e prevedibili);
- **3-5 %** sul braccio FULL (il payload TLS è crittograficamente casuale e quindi impredicibile; la loss ≈ 10 è prossima al massimo teorico ln(65536) ≈ 11.09).

Questo conferma che la cifratura TLS rende il payload effettivamente casuale: il modello non riesce a estrarne pattern.

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
   │  [1] ablate_pcap.py          ← ablazione con Scapy (azzera payload + neutralizza IP/porte)
   ▼
PCAP ablati (HEADER-ONLY e FULL)
   │
   │  [2] vocab_process/main.py   ← costruzione corpus BURST + vocabolario (ET-BERT, con patch)
   │  [3] preprocess.py           ← corpus → dataset binario .pt per il pre-training (ET-BERT)
   ▼
   │  [4] pretrain.py             ← PRE-TRAINING DA ZERO (ET-BERT), un braccio per GPU
   ▼
Modello pre-addestrato (header-only / full)
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

## Risposta alle criticità metodologiche

Questo studio è una riprogettazione rigorosa di un tentativo iniziale che presentava errori metodologici. Le correzioni:

1. **Trasformazione PCAP→TSV esplicita.** L'intera catena parte dai PCAP grezzi ed è documentata e versionata (non si parte più direttamente dai TSV).
2. **Byte inclusi noti e controllati.** Dopo l'ablazione i pacchetti contengono header IP+TCP (con indirizzi e porte azzerati) e payload azzerato o reale a seconda del braccio. Vedi `ablate_pcap.py`.
3. **Scapy effettivamente utilizzato** per l'ablazione (`ablate_pcap.py`).
4. **Niente taglio a lunghezza fissa.** Il vecchio approccio tagliava 104 byte fissi: scorretto perché gli header hanno lunghezza variabile. Ora Scapy separa dinamicamente header e payload sul singolo pacchetto.
5. **Pre-training rifatto da zero** su entrambi i dataset modificati, prima del fine-tuning. Non si usano più corpus/vocab/pesi forniti dagli autori: in questo modo il modello, durante il pre-training, vede gli stessi dati che vedrà nel fine-tuning, eliminando il problema out-of-distribution che invalidava lo studio precedente.

---

## Contenuto del repository

| File | Descrizione |
|---|---|
| `ablate_pcap.py` | Ablazione PCAP con Scapy: azzera payload, neutralizza IP/porte, ricalcola checksum |
| `generate_finetune_tsv.py` | Genera i TSV di fine-tuning (flow-level) dai PCAP ablati |
| `remap_labels.py` | Rende contigui i label (0..N-1) escludendo classi con dati insufficienti |
| `PATCH_ET-BERT.md` | Le modifiche esatte (riga per riga) da applicare a ET-BERT ufficiale |
| `PIPELINE.md` | Tutti i comandi, in ordine, per riprodurre l'esperimento end-to-end |
| `requirements.txt` | Dipendenze aggiuntive rispetto a ET-BERT |

## Licenza e attribuzione

ET-BERT è di Lin et al. ed è soggetto alla loro licenza. Questo repository contiene esclusivamente codice originale e istruzioni di modifica; non ridistribuisce il codice di ET-BERT.
