# Ablation Study su ET-BERT: dove risiede il segnale per classificare il traffico cifrato?

Questo repository contiene il codice e le istruzioni per riprodurre lo studio di ablazione condotto sul modello **ET-BERT** ([Lin et al., WWW 2022](https://github.com/linwhitehat/ET-BERT)), parte della tesi di laurea triennale di Angelo Betza (Sapienza Università di Roma).

## Domanda di ricerca

ET-BERT classifica il traffico di rete cifrato raggiungendo accuratezze molto elevate. La domanda di questa tesi è: **su quali parti del pacchetto si appoggia il modello?** Sul payload cifrato, sugli header di trasporto, o su ciò che resta in chiaro intorno alla cifratura? E la risposta è la stessa su dataset diversi?

Per rispondere, la stessa versione di ET-BERT viene addestrata **da zero** (pre-training + fine-tuning) su tre varianti dello stesso dataset, che differiscono solo per quali byte contengono informazione reale:

| Braccio          | Campi IP/TCP | MAC, IP e porte | Payload      |
| ---------------- | ------------ | --------------- | ------------ |
| **FULL**         | reali        | azzerati        | reale        |
| **HEADER-ONLY**  | reali        | azzerati        | **azzerato** |
| **PAYLOAD-ONLY** | **azzerati** | azzerati        | reale        |

Le parti rimosse vengono **azzerate al loro posto**: i pacchetti mantengono lunghezza e struttura, quindi i tre bracci leggono le stesse posizioni e cambia solo il contenuto. IP, MAC e porte sono azzerati in tutti i bracci per evitare scorciatoie di identificazione. L'impostazione è coerente con le occlusioni *D1* e *P1* di [Wickramasinghe et al., IEEE S&P 2025](https://github.com/nime-sha256/ntc-enigma).

## Risultati

Configurazione principale: fine-tuning **flow-level** (primi 5 pacchetti per flusso, preprocessing originale di ET-BERT), `seq_length` 512, 50 epoche; pre-training da zero di **150.000 step per ogni braccio**.

### CipherSpectrum Mix (41 domini, solo TLS 1.3)

500 flussi per classe, test set di 2.050 campioni. Accuratezza casuale: 2,44%.

| Braccio          | Accuracy | Macro F1 |
| ---------------- | -------- | -------- |
| **FULL**         | 39,71 %  | 34,42 %  |
| **PAYLOAD-ONLY** | 37,80 %  | 32,61 %  |
| **HEADER-ONLY**  | 4,24 %   | 0,40 %   |

### Cross-Platform (202 app Android)

Fino a 500 flussi per classe, test set di 3.207 campioni, stessi flussi in tutti e tre i bracci. Accuratezza casuale: 0,50%.

| Braccio          | Accuracy | Macro F1 |
| ---------------- | -------- | -------- |
| **FULL**         | 98,50 %  | 96,10 %  |
| **HEADER-ONLY**  | 98,44 %  | 95,29 %  |
| **PAYLOAD-ONLY** | 66,01 %  | 44,66 %  |

### Lettura dei risultati

- Su **Cross-Platform** gli header da soli bastano: l'header-only eguaglia il full, pur senza IP né porte, mentre il payload da solo si ferma al 66%. Il dataset è in gran parte non cifrato (circa il 70% dei flussi è HTTP o DNS in chiaro).
- Su **CipherSpectrum** il quadro si rovescia: l'header-only resta vicino al caso, mentre il payload-only si avvicina al full. Il modello non può leggere il contenuto cifrato TLS 1.3; le ipotesi in fase di verifica sono le parti che restano in chiaro nel payload (handshake TLS, lunghezze dei record).
- Nel pre-training, il Masked BURST Model raggiunge un'accuratezza di circa 0,95 sugli header e di circa 0,07 sul payload cifrato, coerente con un payload crittograficamente casuale.

Dettagli in [`RESULTS_cipherspectrum.md`](RESULTS_cipherspectrum.md) e [`RESULTS_crossplatform.md`](RESULTS_crossplatform.md).

> **Nota sulle versioni precedenti.** Una prima versione di questo repository riportava risultati ottenuti con una pipeline diversa (TSV generati con uno script proprio, disallineati rispetto al corpus di pre-training; budget di pre-training diversi tra i bracci; IP e porte non azzerati nell'header-only di Cross-Platform). Quei risultati sono stati sostituiti da quelli sopra e non vanno usati.

## Pipeline

```
PCAP originali
   │  [1] SplitCap                 ← divisione in flussi (solo Cross-Platform)
   │  [2] ablate_pcap.py           ← ablazione con Scapy (codice nostro)
   │  [3] normalize_link.py        ← raw IP → Ethernet (solo Cross-Platform, codice nostro)
   │  [4] filter_valid_cp.py       ← esclusione classi con < 10 flussi validi (solo Cross-Platform)
   ▼
PCAP ablati: FULL / HEADER-ONLY / PAYLOAD-ONLY
   │  [5] vocab_process/main.py    ← corpus BURST (ET-BERT)      lanciato da gen_corpus_*.py
   │  [6] preprocess.py            ← dataset di pre-training (ET-BERT)
   │  [7] pretrain.py              ← pre-training da zero, 150k step (ET-BERT)
   │  [8] data_process/main.py     ← TSV di fine-tuning, flow-level (ET-BERT)   lanciato da run_data_process_*.py
   │  [9] run_classifier.py        ← fine-tuning, 50 epoche (ET-BERT)
   ▼
Risultati
```

Dal passo 5 in poi si usa il codice di ET-BERT, con le sole modifiche di compatibilità descritte in [`PATCH_ET-BERT.md`](PATCH_ET-BERT.md). I comandi completi sono in [`PIPELINE.md`](PIPELINE.md).

## Contenuto del repository

| File | Descrizione |
| --- | --- |
| `ablate_pcap.py` | Ablazione dei PCAP con Scapy: tre modalità, neutralizzazione di MAC/IP/porte, ricalcolo dei checksum |
| `normalize_link.py` | Incapsula in Ethernet i PCAP raw IP, per trattare i due dataset allo stesso modo |
| `filter_valid_cp.py` | Seleziona per Cross-Platform i flussi con almeno 3 pacchetti ed esclude le classi con meno di 10 flussi |
| `gen_corpus_cs_*.py`, `gen_corpus_cp.py` | Lanciano `vocab_process` di ET-BERT sui PCAP ablati |
| `run_data_process_cs.py`, `run_data_process_cp.py` | Lanciano `data_process` di ET-BERT con la configurazione usata |
| `PIPELINE.md` | Tutti i passi e i comandi, in ordine |
| `PATCH_ET-BERT.md`, `patch_*.diff` | Modifiche di compatibilità a ET-BERT |
| `RESULTS_*.md` | Risultati dettagliati per dataset |
| `requirements.txt` | Dipendenze aggiuntive rispetto a ET-BERT |

## Licenza e attribuzione

ET-BERT è di Lin et al. ed è soggetto alla loro licenza. Questo repository contiene esclusivamente codice originale e istruzioni di modifica; non ridistribuisce il codice di ET-BERT.
