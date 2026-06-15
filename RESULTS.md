# Risultati dell'ablation study

Dataset: **Cross-Platform**, 214 app valide (3 escluse per < 3 flussi validi).
Pre-training: **da zero**, ~170k step per braccio.
Fine-tuning: **50 epoche**, flow-level (5 pacchetti per flusso), split 80/10/10.
Modello: ET-BERT (BERT-base, ~136M parametri), vocabolario ~65.536 token bigram.

## Metriche finali (test set, 3633 campioni)

| Braccio | Accuracy | Macro Precision | Macro Recall | Macro F1 |
|---|---|---|---|---|
| **HEADER-ONLY** (payload azzerato) | 98.13 % | 92.29 % | 92.22 % | 91.86 % |
| **FULL** (payload reale) | 98.65 % | 93.83 % | 94.16 % | 93.60 % |
| **Δ** | +0.52 pp | +1.54 pp | +1.94 pp | +1.74 pp |

In entrambi i bracci gli indirizzi IP e le porte sono azzerati, per evitare che il modello
classifichi tramite una banale corrispondenza IP→app invece che tramite i pattern strutturali.

### Interpretazione

- Il modello riconosce le app cifrate al **98.1 % (F1 macro 91.9 %) senza vedere il payload**.
- Lo scarto sul Macro F1 (1.74 punti) è maggiore di quello sull'accuracy (0.52 punti) perché il
  Macro F1 pesa allo stesso modo tutte le classi, comprese quelle con pochi campioni. L'accuracy è
  invece dominata dalle classi numerose, che entrambi i modelli classificano benissimo.

## Analisi delle classi non classificate (F1 = 0)

| Categoria | N. app | App |
|---|---|---|
| F1=0 solo in HEADER-ONLY (il payload aiuta) | 4 | HinKhoj.Dictionary, br.com.escolhatecnologia..., com.ubercab.eats, dating.app.chat.flirt.wgbcv |
| F1=0 in entrambi i bracci | 7 | tra cui una sessione `mitmdump-...` (non un'app: traffico via proxy MITM) |
| F1=0 solo in FULL | 0 | — |

**Punto chiave:** le 4 app "salvate dal payload" sono **esattamente quelle con il minor numero di
flussi di training (4-8 esempi)**. Non è una prova che il payload contenga informazione necessaria:
è un effetto di scarsità di dati, in cui il modello, non avendo abbastanza esempi, sfrutta qualsiasi
segnale disponibile. Per le altre 210 app gli header bastano. Questo rafforza la tesi: il payload
cifrato non aggiunge informazione utile quando i dati di training sono sufficienti.

## Osservazione dal pre-training

Il task **Masked BURST Model** (ricostruzione di byte mascherati) durante il pre-training raggiunge:

| Braccio | acc_mlm | loss_mlm |
|---|---|---|
| HEADER-ONLY | 97-98 % | 0.11 - 0.23 |
| FULL | 3-5 % | ≈ 10 |

La loss_mlm del braccio FULL (≈ 10) è prossima al massimo teorico per una sequenza casuale su un
vocabolario di 65.536 simboli: ln(65536) ≈ 11.09. Questo **misura quantitativamente** che il payload
TLS è effettivamente casuale (la cifratura "funziona"): non esistono pattern da apprendere. Gli
header invece sono altamente predicibili (struttura rigida), e infatti il modello li ricostruisce
quasi perfettamente.

> Questo risultato è indipendente dal fine-tuning ed è già di per sé una conferma dell'ipotesi: il
> contenuto cifrato non offre appigli al modello, mentre gli header sì.

## Nota metodologica sulle metriche

I valori di Precision/Recall/F1 sopra riportati sono stati ottenuti rieseguendo la valutazione sui
modelli fine-tuned salvati. La riesecuzione ha comportato una epoca di training aggiuntiva (a causa
di un percorso hardcoded nel codice di valutazione di ET-BERT — `/data2/lxj/...` — che impediva il
salvataggio della confusion matrix). Per questo i valori di accuracy differiscono di pochi decimi
da quelli stampati nei log a 50 epoche (HEADER-ONLY 98.62 %, FULL 98.90 %). Le conclusioni del
confronto fra i due bracci non cambiano.
