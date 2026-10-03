# Modifiche a ET-BERT

Questo repository non ridistribuisce il codice di ET-BERT, che resta soggetto
alla licenza dei suoi autori. Qui sono elencate le modifiche da applicare alla
release ufficiale per riprodurre gli esperimenti.

Le modifiche sono di sola compatibilita' con l'ambiente di esecuzione: percorsi
Windows sostituiti con percorsi Linux, caricamento del modello su una sola GPU,
percorso di scrittura della matrice di confusione. **La logica di
preprocessing, tokenizzazione e addestramento non e' stata modificata.**

In particolare, l'offset con cui vengono scartati i primi byte di ogni pacchetto
(i primi 76 caratteri esadecimali, pari a 38 byte: header Ethernet, header IP e
porte) e' quello originale di ET-BERT, sia nel corpus di pre-training sia nei
dati di fine-tuning.

## 1. `vocab_process/main.py`

Genera il corpus BURST e il vocabolario. Modifiche:

- `word_dir`: da `"I:/corpora/"` a `"./datasets/"`;
- selezione dei file: da un filtro specifico per il dataset originale
  (`if "pcapng" not in file and tls13_name in file`) a `if file.endswith(".pcap")`;
- costruzione dei percorsi: da separatore Windows (`parent + "\\" + file`) a
  separatore POSIX (`parent + "/" + file`);
- `processors.BertProcessing`: chiamata con argomenti posizionali, per
  compatibilita' con la versione della libreria `tokenizers` in uso;
- percorso di scrittura del vocabolario: sostituito con un percorso locale sotto
  `datasets/`.

Il vocabolario prodotto contiene 65.536 token, cioe' tutte le coppie di byte
possibili, piu' i cinque token speciali `[PAD]`, `[SEP]`, `[CLS]`, `[UNK]`,
`[MASK]`. E' unico e condiviso da tutti i bracci sperimentali.

Diff: `patch_vocab_main.diff`

## 2. `fine-tuning/run_classifier.py`

Modifiche:

- aggiunta di `sys.path.append(".")`, per permettere l'import dei moduli
  ausiliari presenti nella directory di lavoro sul server;
- `load_or_initialize_parameters`: `map_location` semplificato a `'cuda:0'`, al
  posto della mappatura multi-GPU dell'originale, perche' gli esperimenti girano
  su una singola GPU per volta;
- percorso di scrittura della matrice di confusione: sostituito il percorso
  assoluto degli autori con uno locale sotto `results/`.

Diff: `patch_run_classifier.diff`

## 3. `data_process/dataset_generation.py`

**Non modificato.** Viene usato nella versione originale, con i parametri di
default: `dataset_level = "flow"`, cinque pacchetti per flusso, fino a 128 token
per pacchetto, offset a 76 caratteri esadecimali.

La configurazione (numero di classi, campioni per classe, livello di
granularita') viene passata da uno script di lancio esterno che importa il
modulo, senza toccarne il codice: si veda `run_data_process_cs.py`.

## Nota storica

Una versione precedente di questo lavoro generava i dati di fine-tuning con uno
script proprio (`generate_finetune_tsv.py`, ora in `deprecated/`) che scartava
solo i primi 28 caratteri esadecimali, contro i 76 usati dal corpus di
pre-training. Le due fasi risultavano quindi disallineate di 38 byte. La
pipeline attuale usa `data_process` di ET-BERT anche per il fine-tuning, quindi
l'offset e' lo stesso ovunque.
