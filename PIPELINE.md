# Pipeline completa di riproduzione

Tutti i comandi, in ordine, per riprodurre lo studio end-to-end a partire dai PCAP grezzi.
Sostituire i percorsi con i propri. L'esempio usa il dataset Cross-Platform.

## Setup iniziale

```bash
# Clona ET-BERT ufficiale e applica le patch (vedi PATCH_ET-BERT.md)
git clone https://github.com/linwhitehat/ET-BERT.git
cd ET-BERT

# Ambiente
python3 -m venv etbert_env
source etbert_env/bin/activate
pip install scapy scikit-learn xlrd
pip install -r requirements.txt   # requisiti di ET-BERT/UER

# Applica le patch agli offset (Patch 1)
sed -i 's/\[76:\]/[28:]/g; s/decode()\[:2\*payload_len\]/decode()[28:28+2*payload_len]/g' data_process/dataset_generation.py
# (+ le altre patch di portabilità e di percorso, vedi PATCH_ET-BERT.md)

# Copia gli script di questo repo nella root di ET-BERT
cp /percorso/repo/ablate_pcap.py .
cp /percorso/repo/generate_finetune_tsv.py .
cp /percorso/repo/remap_labels.py .
```

---

## [1] Ablazione dei PCAP con Scapy

Genera i due dataset: HEADER-ONLY (payload azzerato) e FULL (payload reale). In entrambi gli
indirizzi IP e le porte vengono azzerati.

```bash
# Braccio HEADER-ONLY (payload azzerato — default)
python3 ablate_pcap.py  /percorso/pcap_grezzi  /percorso/pcap_ablato_headeronly

# Braccio FULL (payload reale)
python3 ablate_pcap.py  /percorso/pcap_grezzi  /percorso/pcap_full_baseline  --keep-payload
```

Verifica che le dimensioni dei PCAP siano preservate (la lunghezza dei pacchetti non deve cambiare).

---

## [2] Corpus BURST + vocabolario (per il pre-training)

Si usa `vocab_process/main.py` di ET-BERT. Configurare i percorsi nel file (vedi commenti nel
codice) per puntare al dataset ablato e per generare prima il corpus, poi il vocabolario.

```bash
# Esempio per HEADER-ONLY (configurare pcap_dir e word_name nel file)
python3 vocab_process/main.py
```

Produce: il corpus testuale dei BURST (`*_burst.txt`) e il file di vocabolario (`*_vocab.txt`,
~65k token bigram). Ripetere puntando al dataset FULL per generare il corpus FULL.

---

## [3] Corpus → dataset binario `.pt`

Si usa `preprocess.py` di ET-BERT.

```bash
# HEADER-ONLY
python3 preprocess.py \
  --corpus_path datasets/<corpus_headeronly>.txt \
  --vocab_path  datasets/<vocab>.txt \
  --dataset_path datasets/pretrain_headeronly.pt \
  --seq_length 512 --processes_num 8 --target bert

# FULL (analogo, con il corpus FULL → pretrain_full.pt)
```

---

## [4] Pre-training DA ZERO

Si usa `pre-training/pretrain.py` di ET-BERT. Un braccio per GPU. **Non si parte dai pesi degli
autori**: il modello è inizializzato da zero.

```bash
# HEADER-ONLY su una GPU (es. GPU 4)
PYTHONPATH=$(pwd) CUDA_VISIBLE_DEVICES=4 \
python3 pre-training/pretrain.py \
  --dataset_path datasets/pretrain_headeronly.pt \
  --vocab_path   datasets/<vocab>.txt \
  --config_path  models/bert_base_config.json \
  --output_model_path models/pretrained_headeronly.bin \
  --world_size 1 --gpu_ranks 0 \
  --total_steps 500000 --save_checkpoint_steps 10000 \
  --report_steps 500 --batch_size 32 \
  --embedding word_pos_seg --encoder transformer \
  --mask fully_visible --target bert

# FULL su un'altra GPU (es. GPU 5), comando analogo con i file _full
```

Nota: nei risultati riportati il pre-training è stato interrotto a ~170k step per entrambi i bracci
(stesso numero di step per garantire un confronto equo), una volta osservata la convergenza della
loss. Il pre-training salva un checkpoint ogni 10k step (`...bin-170000`).

---

## [5] TSV di fine-tuning (flow-level)

Codice di questo repo. Estrae feature a livello di flusso (5 pacchetti per flusso) dai PCAP ablati,
saltando i primi 14 byte (Ethernet) e applicando la tokenizzazione bigram. Split 80/10/10.

```bash
# HEADER-ONLY
python3 generate_finetune_tsv.py \
  --pcap_dir   /percorso/pcap_ablato_headeronly \
  --output_dir datasets/finetune_headeronly \
  --samples_per_class 500

# FULL
python3 generate_finetune_tsv.py \
  --pcap_dir   /percorso/pcap_full_baseline \
  --output_dir datasets/finetune_full \
  --samples_per_class 500
```

Produce `train/valid/test_dataset.tsv` + `label_map.txt`.

---

## [6] Rimappatura dei label

Codice di questo repo. Rende i label contigui (0..N-1) ed esclude classi con dati insufficienti
(< 3 flussi), così ET-BERT non va modificato.

```bash
python3 remap_labels.py datasets/finetune_headeronly datasets/finetune_full
```

Aggiunge anche l'intestazione `label\ttext_a` richiesta da `run_classifier.py`.

---

## [7] Fine-tuning (50 epoche)

Si usa `fine-tuning/run_classifier.py` di ET-BERT, partendo dal checkpoint pre-addestrato del
braccio corrispondente. Un braccio per GPU.

```bash
# HEADER-ONLY su GPU 4
PYTHONPATH=$(pwd) CUDA_VISIBLE_DEVICES=4 \
python3 fine-tuning/run_classifier.py \
  --pretrained_model_path models/pretrained_headeronly.bin-170000 \
  --vocab_path   datasets/<vocab>.txt \
  --config_path  models/bert_base_config.json \
  --train_path   datasets/finetune_headeronly/train_dataset.tsv \
  --dev_path     datasets/finetune_headeronly/valid_dataset.tsv \
  --test_path    datasets/finetune_headeronly/test_dataset.tsv \
  --output_model_path models/finetuned_headeronly.bin \
  --epochs_num 50 --batch_size 32 --seq_length 512 \
  --learning_rate 6e-5 \
  --embedding word_pos_seg --encoder transformer --mask fully_visible \
  --report_steps 100

# FULL su GPU 5, comando analogo con i file _full
```

L'accuratezza sul test set viene stampata a fine training. La confusion matrix viene salvata in
`results/confusion_matrix` (dopo Patch 3).

---

## Parametri chiave usati

| Parametro | Valore |
|---|---|
| Modello | ET-BERT (BERT-base: 12 layer, 12 teste, hidden 768, ~136M parametri) |
| Vocabolario | ~65.536 token bigram (2 byte) |
| seq_length | 512 |
| Pacchetti per flusso (fine-tuning) | 5 |
| Pre-training | da zero, ~170k step, batch 32, lr 2e-5 |
| Fine-tuning | 50 epoche, batch 32, lr 6e-5 |
| Split train/valid/test | 80/10/10 |
| GPU | 2× NVIDIA RTX A6000 (una per braccio) |
