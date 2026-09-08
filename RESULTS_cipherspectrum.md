# Risultati dell'ablation study — CipherSpectrum

Dataset: **CipherSpectrum (mix)**, 41 domini, TLS 1.3 con cifrari moderni
(AES-128-GCM, AES-256-GCM, ChaCha20-Poly1305 mescolati).
Cattura in ambiente virtualizzato (IP sorgente unico `10.0.2.15`).

Pre-training: da zero, 500.000 step per braccio (arrivati naturalmente a convergenza).
Fine-tuning: 50 epoche, flow-level, `seq_length` 512.
In tutti i bracci IP e porte sono azzerati (via Scapy) per evitare scorciatoie di identificazione.

## Metriche finali (test set, ultima epoca)

| Braccio        | Accuracy | Macro Precision | Macro Recall | Macro F1 |
|----------------|----------|-----------------|--------------|----------|
| PAYLOAD-ONLY   | 33.66%   | 40.34%          | 33.66%       | 29.80%   |
| FULL baseline  | 25.71%   | 31.00%          | 32.49%       | 28.01%   |
| HEADER-ONLY    | 4.59%    | 0.22%           | 4.59%        | 0.43%    |

(Livello del caso su 41 classi bilanciate = 2.44%.)

## Osservazione chiave — il contrasto con Cross-Platform

Il risultato è l'**opposto** di quanto osservato su Cross-Platform:

| Braccio      | Cross-Platform | CipherSpectrum |
|--------------|----------------|----------------|
| HEADER-ONLY  | 98.13%         | 4.59%          |
| PAYLOAD-ONLY | 1.38%          | 33.66%         |
| FULL         | 98.65%         | 25.71%         |

- Su Cross-Platform il segnale utile stava **negli header** (bastavano da soli).
- Su CipherSpectrum il segnale utile sta **nel payload** — payload-only eguaglia
  e supera il traffico completo; gli header da soli collassano quasi al livello del caso.

La conclusione "per classificare bastano gli header" dei lavori originali **non è universale**:
dipende dal dataset e dal metodo di cattura.

## Perché gli header di CipherSpectrum portano poco segnale

Misura diretta sui pacchetti di risposta del server: su 58 posizioni-byte dell'header,
**solo 13 (22%) variano tra i domini**; le altre 45 (78%) sono costanti per tutti i siti.
Probabile effetto dell'ambiente di cattura virtualizzato e uniforme (stesso client,
stesso stack di rete per tutte le catture).

## Nota importante sul payload cifrato

Il 33% ottenuto da payload-only **NON** significa che il modello legge il contenuto cifrato.
Il modello sfrutta i **metadati che restano visibili nonostante la cifratura**:
lunghezze dei pacchetti/record, pattern di trasmissione. È un canale laterale noto
in letteratura (traffic/website fingerprinting), non una violazione della crittografia.

## Analisi degli errori (matrice di confusione)

- Un nucleo ristretto di **servizi di tracciamento di terze parti**
  (google-analytics, googletagmanager, doubleclick, hotjar, hubspot, segment, onetrust)
  si confonde sistematicamente tra loro: richieste strutturalmente quasi identiche.
- HEADER-ONLY non "sbaglia", **collassa**: interi domini vengono riversati al 100%
  in pochi attrattori (es. like-video.com → mozilla.net, 50/50 casi).
- `mozilla.net` è l'unico dominio classificato perfettamente (P=R=F1=1.0) in ogni braccio:
  pattern di traffico evidentemente molto distintivo.

## Dal pre-training

- HEADER-ONLY: `acc_mlm` sale rapidamente a ~95% (compito facile, dominato dai byte zero del padding).
- FULL / PAYLOAD-ONLY: `acc_mlm` sale lentamente (0 → ~75-79%), coerente con payload
  cifrato genuinamente difficile da predire.
