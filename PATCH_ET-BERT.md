# Modifiche da applicare a ET-BERT ufficiale

Questo studio usa [ET-BERT ufficiale](https://github.com/linwhitehat/ET-BERT) con poche modifiche mirate.
I numeri di riga si riferiscono al codice del repository ufficiale al momento della clonazione
(`git clone https://github.com/linwhitehat/ET-BERT.git`). Verificare con `grep` se la numerazione
differisse in versioni successive.

---

## Patch 1 — Offset di slicing dei byte: `[76:]` → `[28:]`

### Motivazione

ET-BERT, prima di tokenizzare un pacchetto, scarta un numero fisso di caratteri esadecimali
dall'inizio. Nel codice originale scarta **76 caratteri esadecimali = 38 byte**, che corrispondono a:

- header Ethernet (14 byte)
- header IP (20 byte)
- porte TCP, sorgente + destinazione (4 byte)

Questo butta via **l'intero header IP** (TTL, identificativo, flag, lunghezza totale), che sono
proprio i campi strutturali che vogliamo analizzare nello studio. Inoltre l'offset 76 è corretto
**solo per IPv4 senza opzioni**: con IPv6 (header di 40 byte) l'offset cade in mezzo all'header,
producendo token privi di senso.

### Soluzione

Si scartano solo i **28 caratteri esadecimali = 14 byte** dell'header Ethernet. In questo modo il
modello vede l'header IP completo + l'header TCP completo. Gli indirizzi IP e le porte vengono
neutralizzati a monte da `ablate_pcap.py` (azzerati), quindi non costituiscono una scorciatoia.

Questa modifica corregge anche un'**incoerenza interna di ET-BERT**: la funzione usata per il
pre-training (`get_burst_feature`) e quella per il fine-tuning (`get_feature_packet`/`get_feature_flow`)
usavano offset diversi, facendo vedere al modello layout di byte diversi nelle due fasi.

### File: `data_process/dataset_generation.py`

| Riga | Funzione | Prima | Dopo |
|---|---|---|---|
| 109 | `get_burst_feature` (pre-training) | `data.decode()[:2*payload_len]` | `data.decode()[28:28+2*payload_len]` |
| 147 | `get_feature_packet` (fine-tuning packet) | `packet_string[76:]` | `packet_string[28:]` |
| 199 | `get_feature_flow` (fine-tuning flow) | `data.decode()[76:]` | `data.decode()[28:]` |
| 205 | `get_feature_flow` (fine-tuning flow) | `data.decode()[76:]` | `data.decode()[28:]` |

### File: `vocab_process/main.py`

| Riga | Prima | Dopo |
|---|---|---|
| 64 | `words.decode()[76:]` | `words.decode()[28:]` |

### Comando per applicarle tutte

```bash
cp data_process/dataset_generation.py data_process/dataset_generation.py.bak
cp vocab_process/main.py vocab_process/main.py.bak

sed -i 's/\[76:\]/[28:]/g; s/decode()\[:2\*payload_len\]/decode()[28:28+2*payload_len]/g' \
    data_process/dataset_generation.py
sed -i 's/\[76:\]/[28:]/g' vocab_process/main.py

# Verifica: deve restituire 0 righe
grep -nE "\[76:\]|decode\(\)\[:2\*payload_len\]" data_process/dataset_generation.py vocab_process/main.py
```

> **Nota:** la patch va applicata anche a `vocab_process/main.py`, ma poiché il corpus di
> pre-training di questo studio è stato generato prima di questa correzione su `vocab_process`,
> nei risultati riportati esiste una lieve asimmetria documentata in fondo a questo file.
> La patch è comunque inclusa per chi voglia una pipeline pienamente coerente.

---

## Patch 2 — Adattamenti di portabilità Windows → Linux

Il codice di ET-BERT contiene percorsi e separatori in stile Windows. Su Linux:

- In `vocab_process/main.py`: sostituire i percorsi hardcoded (es. `I:/corpora/`) con percorsi
  locali (es. `./datasets/`), e i separatori `\\` con `/` nella costruzione dei nomi file.
- In `vocab_process/main.py`: il filtro sui file PCAP basato sul nome (`tls13_name`) va reso
  generico (controllo dell'estensione `.pcap`) per funzionare con dataset diversi da CSTNET-TLS 1.3.

## Patch 3 — Percorso hardcoded della confusion matrix

In `fine-tuning/run_classifier.py`, riga 227, il percorso di salvataggio della confusion matrix è
hardcoded all'ambiente degli autori:

```python
with open("/data2/lxj/pre-train/results/confusion_matrix",'w') as f:
```

Sostituirlo con un percorso locale:

```bash
mkdir -p results
sed -i 's|/data2/lxj/pre-train/results/confusion_matrix|./results/confusion_matrix|g' \
    fine-tuning/run_classifier.py
```

## Patch 4 — Compatibilità tokenizer con librerie aggiornate

Con versioni recenti della libreria `tokenizers`, in `vocab_process/main.py` può essere necessario
rimuovere i parametri `sep=` e `cls=` nella chiamata a `processors.BertProcessing`, non più
supportati nella stessa forma.

---

## Nota sui label (gestita da codice nostro, ET-BERT non modificato)

`fine-tuning/run_classifier.py` (riga 79) calcola il numero di classi come numero di label distinti
nel training set. Se i label non sono contigui (0,1,…,99,101,…) il modello crea meno neuroni di
output dei necessari e fallisce a runtime. Invece di modificare ET-BERT, rendiamo i label contigui
con `remap_labels.py` (incluso in questo repo) **prima** del fine-tuning. Così ET-BERT resta intatto.

---

## Limitazione nota

Nei risultati riportati, il corpus di pre-training è stato generato con `vocab_process/main.py`
ancora con offset `[76:]`, mentre il fine-tuning usa l'offset corretto `[28:]`. Esiste quindi una
lieve asimmetria tra i byte visti in pre-training e in fine-tuning. **Questa asimmetria si applica
in egual misura a entrambi i bracci (HEADER-ONLY e FULL)**, quindi non altera il confronto, che è
l'oggetto dello studio. Per una pipeline pienamente coerente, rigenerare il corpus di pre-training
dopo aver applicato la Patch 1 anche a `vocab_process/main.py` (riga 64).
