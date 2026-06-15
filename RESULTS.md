# Risultati dell'ablation study

Dataset: Cross-Platform, 214 app valide (3 escluse per dati insufficienti)
Pre-training: da zero, ~170k step per braccio
Fine-tuning: 50 epoche, flow-level (5 pacchetti per flusso)

## Metriche finali (test set)

| Braccio       | Accuracy | Macro Precision | Macro Recall | Macro F1 |
|---------------|----------|-----------------|--------------|----------|
| HEADER-ONLY   | 98.13%   | 92.29%          | 92.22%       | 91.86%   |
| FULL baseline | 98.65%   | 93.83%          | 94.16%       | 93.60%   |
| Delta         | +0.52 pp | +1.54 pp        | +1.94 pp     | +1.74 pp |

## Osservazione chiave

- 203/214 app classificate correttamente da entrambi i modelli
- 4 app con F1=0 solo in header-only: tutte con 4-8 flussi di training
- 7 app con F1=0 in entrambi: dati insufficienti o traffico anomalo

## Dal pre-training

Task Masked BURST Model:
- HEADER-ONLY: acc_mlm 97-98% (header strutturati e prevedibili)
- FULL: acc_mlm 3-5% (payload TLS casuale; loss ~10 vicino a ln(65536)=11.09)
