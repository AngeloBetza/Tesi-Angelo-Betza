# Risultati su Cross-Platform

**Dataset:** Cross-Platform, sottoinsieme Android. 217 cartelle originali, 68.005 flussi. Esclusi:
- le app con meno di 10 flussi validi (almeno 3 pacchetti), insufficienti per una divisione stratificata;
- 3 app per cui il preprocessing di ET-BERT lascia meno di 2 campioni.

Classi finali: 202. Divisione 25.652 / 3.207 / 3.207. Accuratezza casuale: 0,50%.

Composizione dei flussi per protocollo e porta: HTTP/80 40,6%, DNS/53 27,9%, HTTPS/443 22,1%, altro 9,4%. La maggior parte del traffico non è cifrata.

**Configurazione:** come CipherSpectrum (pre-training da zero a 150.000 step per braccio, fine-tuning flow-level, 50 epoche, `seq_length` 512), con al massimo 500 flussi per classe. I PCAP, in formato raw IP, sono normalizzati a Ethernet prima della pipeline.

## Risultati principali

| Braccio | Accuracy | Macro P | Macro R | Macro F1 | Classi con F1 = 0 |
|---|---|---|---|---|---|
| FULL | 98,50 % | 96,56 % | 96,71 % | 96,10 % | 1 / 202 |
| HEADER-ONLY | 98,44 % | 95,75 % | 95,68 % | 95,29 % | 4 / 202 |
| PAYLOAD-ONLY | 66,01 % | 48,02 % | 44,48 % | 44,66 % | 50 / 202 |

## Allineamento dei flussi tra i bracci

Il `data_process` di ET-BERT ricostruisce i flussi con tshark e scarta quelli che non riesce a usare. Questo passo dipende dagli header: quando sono azzerati, come nel braccio PAYLOAD-ONLY, mancano flag e porte e vengono scartati flussi diversi. Nella prima generazione dei dati il braccio PAYLOAD-ONLY aveva circa il 13% di campioni di training in più degli altri due, distribuiti diversamente tra le classi.

Per confrontare i bracci sugli stessi dati, il braccio PAYLOAD-ONLY è stato rigenerato usando solo i flussi accettati nel braccio FULL (`check_eligible_cp.py`, `run_data_process_cp_matched.py`), con lo stesso numero di campioni per classe. I tre bracci hanno ora esattamente gli stessi campioni di training e di test in ogni classe.
