# Risultati dell'ablation study

Dataset: **Cross-Platform**, 214 app valide (3 escluse per < 3 flussi validi).
Pre-training: **da zero**, per ogni braccio separatamente.
Fine-tuning: **50 epoche**, flow-level (5 pacchetti per flusso), split 80/10/10.
Modello: ET-BERT (BERT-base, ~136M parametri), vocabolario ~65.536 token bigram.

## Metriche finali (test set, 3633 campioni)

| Braccio | Cosa vede | Accuracy | Macro Precision | Macro Recall | Macro F1 | Classi F1=0 |
|---|---|---|---|---|---|---|
| **FULL** (baseline) | Header reali + payload TLS reale | 98.65% | 93.83% | 94.16% | 93.60% | 7/214 |
| **HEADER-ONLY** | Header reali + payload azzerato | 98.13% | 92.29% | 92.22% | 91.86% | 11/214 |
| **PAYLOAD-ONLY** | Header azzerati + payload TLS reale | 1.38% | 0.01% | 0.47% | 0.01% | 213/214 |

In tutti e tre i bracci gli indirizzi IP e le porte sono azzerati.

## Conclusione

- **HEADER-ONLY ≈ FULL**: gli header contengono quasi tutta l'informazione necessaria
  per classificare le app (differenza di soli 1.74 punti di F1 macro).
- **PAYLOAD-ONLY ≈ caso casuale** (1/214 = 0.47%): il payload cifrato da solo
  è completamente inutile per la classificazione.

ET-BERT non sta "entrando" nel traffico cifrato. Sta leggendo la firma strutturale
degli header (dimensioni pacchetti, flag TCP, TTL, window size, pattern seq/ack),
esattamente come un sistema di fingerprinting passivo classico. Il payload TLS è
crittograficamente casuale e non porta informazione classificabile.

## Analisi delle classi non classificate

Le 4 app con F1=0 solo in HEADER-ONLY (classificate dal FULL) hanno tutte ≤8 flussi
di training: è un effetto di scarsità di dati, non prova che il payload sia necessario.

Nel braccio PAYLOAD-ONLY, 213/214 app hanno F1=0: il modello assegna quasi tutto
al caso, confermando che il payload TLS non porta pattern classificabili.

## Dal pre-training (task Masked BURST Model)

| Braccio | acc_mlm | loss_mlm | Interpretazione |
|---|---|---|---|
| HEADER-ONLY | 97-98% | 0.11-0.23 | Header strutturati e prevedibili |
| FULL | 3-5% | ~10 | Payload TLS casuale domina |
| PAYLOAD-ONLY | 0.3-1.3% | ~10.8 | Payload TLS casuale + header azzerati |

La loss_mlm teorica massima per dati casuali su vocabolario di 65.536 simboli è
ln(65536) ≈ 11.09. I valori di FULL e PAYLOAD-ONLY si avvicinano a questo limite,
confermando che il payload TLS è effettivamente casuale e impredicibile.
