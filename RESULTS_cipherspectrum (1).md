# Risultati su CipherSpectrum

**Dataset:** CipherSpectrum Mix, 41 domini, solo TLS 1.3; in ogni classe sono presenti sessioni cifrate con tutti e tre i cipher suite AEAD (AES-128-GCM, AES-256-GCM, ChaCha20-Poly1305).

**Configurazione:**
- pre-training da zero, 150.000 step per ogni braccio, vocabolario condiviso (65.536 coppie di byte + 5 token speciali);
- fine-tuning flow-level con `data_process` di ET-BERT (primi 5 pacchetti per flusso), 500 flussi per classe, divisione 80/10/10 (16.400 / 2.050 / 2.050);
- 50 epoche, batch 32, `seq_length` 512, learning rate 6e-5.

Accuratezza casuale: 2,44%.

## Risultati principali

| Braccio | Accuracy | Macro P | Macro R | Macro F1 | Classi con F1 = 0 |
|---|---|---|---|---|---|
| FULL | 39,71 % | 38,49 % | 39,71 % | 34,42 % | 8 / 41 |
| PAYLOAD-ONLY | 37,80 % | 34,56 % | 37,80 % | 32,61 % | 8 / 41 |
| HEADER-ONLY | 4,24 % | 0,21 % | 4,24 % | 0,40 % | 39 / 41 |

Il valore del braccio FULL è coerente con quello ottenuto in modo indipendente sullo stesso dataset (circa 37%).

## Effetto del budget di pre-training (braccio FULL)

Stessi dati e stesso fine-tuning, cambia solo il checkpoint di partenza:

| Step di pre-training | Accuracy |
|---|---|
| 80.000 | 6,83 % |
| 150.000 | 39,71 % |
| 500.000 | 33,71 % |

Le metriche del pre-training si stabilizzano molto prima delle prestazioni a valle: l'accuratezza del Masked BURST Model non è un buon criterio per decidere quando fermarsi.

## Metriche di pre-training

| Braccio | Step | acc_mlm | loss_mlm |
|---|---|---|---|
| HEADER-ONLY | 160.000 | 0,95 | 0,49 |
| FULL | 500.000 | 0,75 | 1,78 |
| PAYLOAD-ONLY | 150.000 | 0,07 | 10,15 |

Sul payload cifrato il modello non riesce a prevedere i token mascherati: la loss resta vicina al massimo teorico, ln(65536) ≈ 11,09.

## Cosa vede il modello

Per ogni pacchetto il preprocessing di ET-BERT scarta i primi 38 byte (Ethernet, header IP, porte) e legge al massimo 128 token, cioè circa 129 byte. Su CipherSpectrum i campioni hanno in media 271 token (massimo 326), perché tre dei cinque pacchetti sono l'handshake TCP. Ne segue che il braccio HEADER-ONLY vede solo i campi TCP dal numero di sequenza in poi, opzioni comprese, seguiti da zeri.
