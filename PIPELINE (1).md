# Pipeline completa

Sequenza dei comandi per riprodurre l'esperimento end-to-end, per un braccio
alla volta. I bracci sono tre: `full`, `headeronly`, `payloadonly`.

Rispetto alla prima versione di questa pipeline sono cambiate due cose:

- i TSV di fine-tuning vengono generati con `data_process` di ET-BERT e non
  piu' con uno script proprio, cosi' corpus di pre-training e dati di
  fine-tuning usano la stessa tokenizzazione e lo stesso offset;
- per Cross-Platform e' stato aggiunto un passo di normalizzazione del link
  layer, perche' quei PCAP sono raw IP e non Ethernet.

## 0. Prerequisiti

Repository ufficiale di ET-BERT, ambiente virtuale con le dipendenze di
`requirements.txt`, e le patch descritte in `PATCH_ET-BERT.md`.

```bash
cd ~/ET-BERT-main
source etbert_env/bin/activate
export PYTHONPATH=$HOME/ET-BERT-main
```

## 1. Divisione in flussi

I PCAP originali vengono divisi in un file per flusso (5-tupla) con SplitCap.
CipherSpectrum e' gia' distribuito con un file per sessione, quindi il passo
riguarda solo Cross-Platform.

## 2. Ablazione

```bash
python3 ablate_pcap.py --keep-payload  PCAP_DIR  OUT_full
python3 ablate_pcap.py                 PCAP_DIR  OUT_headeronly
python3 ablate_pcap.py --payload-only  PCAP_DIR  OUT_payloadonly
```

Controllare nell'output che `Intatti` sia 0: se non lo e', Scapy non e'
riuscito a interpretare alcuni pacchetti e l'ablazione non li ha modificati.

## 3. Normalizzazione del link layer (solo Cross-Platform)

```bash
python3 normalize_link.py OUT_full         OUT_full_eth
python3 normalize_link.py OUT_headeronly   OUT_headeronly_eth
python3 normalize_link.py OUT_payloadonly  OUT_payloadonly_eth
```

Verifica: il primo pacchetto deve iniziare con dodici byte a zero, poi `08 00`,
poi `45`.

```bash
python3 -c "
from scapy.all import rdpcap; import glob
print(bytes(rdpcap(glob.glob('OUT_full_eth/*/*.pcap')[0])[0])[:24].hex(' '))"
```

## 4. Corpus di pre-training

Uno script di lancio per braccio, che configura `vocab_process/main.py` di
ET-BERT (vedi `gen_corpus_cs_full.py` come esempio):

```python
import sys
sys.path.insert(0, "/percorso/ET-BERT-main/vocab_process")
import main as m
m.pcap_dir  = "/percorso/dataset_ablato/"
m.word_dir  = "/percorso/ET-BERT-main/datasets/"
m.word_name = "cs_burst_full.txt"
m.preprocess(m.pcap_dir)
```

Il vocabolario (`cs_vocab.txt`) e' quello di ET-BERT: 65.536 coppie di byte
piu' i cinque token speciali. E' unico e condiviso da tutti i bracci.

## 5. Preprocess

Ogni braccio in una cartella temporanea propria, per evitare collisioni dei
file `dataset-tmp-*.pt`:

```bash
mkdir -p tmp_preprocess_ARM && cd tmp_preprocess_ARM
python3 -u ../preprocess.py \
  --corpus_path  ../datasets/cs_burst_ARM.txt \
  --vocab_path   ../datasets/cs_vocab.txt \
  --dataset_path ../datasets/cs_pretrain_ARM.pt \
  --seq_length 512 --processes_num 16 --target bert
```

## 6. Pre-training

```bash
CUDA_VISIBLE_DEVICES=N python3 -u pre-training/pretrain.py \
  --dataset_path datasets/cs_pretrain_ARM.pt \
  --vocab_path   datasets/cs_vocab.txt \
  --config_path  models/bert_base_config.json \
  --output_model_path models/cs_pretrained_ARM.bin \
  --total_steps 150000 --save_checkpoint_steps 5000 --report_steps 500 \
  --batch_size 32 --embedding word_pos_seg --encoder transformer \
  --mask fully_visible --target bert --world_size 1 --gpu_ranks 0
```

Il numero di step deve essere lo stesso per tutti e tre i bracci, altrimenti il
confronto non e' valido. Per riprendere da un checkpoint si aggiunge
`--pretrained_model_path models/cs_pretrained_ARM.bin-<step>`.

## 7. TSV di fine-tuning

Con `data_process/main.py` di ET-BERT, configurato da uno script di lancio
(`run_data_process_cs.py`):

```python
m._category     = 41            # numero di classi
m.samples       = [500] * 41    # campioni per classe
m.features      = ["payload"]
m.dataset_level = "flow"        # primi 5 pacchetti per flusso
```

Divisione train/valid/test 80/10/10. Se i label non sono contigui, si usa
`remap_labels.py`.

## 8. Fine-tuning

```bash
CUDA_VISIBLE_DEVICES=N python3 -u fine-tuning/run_classifier.py \
  --pretrained_model_path models/cs_pretrained_ARM.bin-150000 \
  --vocab_path   datasets/cs_vocab.txt \
  --config_path  models/bert_base_config.json \
  --train_path   datasets/finetune_cs_ARM_dp/train_dataset.tsv \
  --dev_path     datasets/finetune_cs_ARM_dp/valid_dataset.tsv \
  --test_path    datasets/finetune_cs_ARM_dp/test_dataset.tsv \
  --output_model_path models/cs_finetuned_ARM.bin \
  --epochs_num 50 --batch_size 32 --seq_length 512 --learning_rate 6e-5 \
  --embedding word_pos_seg --encoder transformer --mask fully_visible \
  --report_steps 100
```

## Verifiche consigliate

Prima di lanciare un pre-training lungo conviene controllare che i dati siano
quelli attesi, perche' un'ablazione puo' fallire in silenzio.

Byte effettivamente presenti nei PCAP ablati:

```bash
python3 -c "
from scapy.all import rdpcap; import glob
p = [x for x in rdpcap(glob.glob('OUT_headeronly/*/*.pcap')[0]) if len(bytes(x))>100][0]
b = bytes(p); print('header :', b[:40].hex(' ')); print('payload:', b[40:80].hex(' '))"
```

Token sconosciuti nei TSV rispetto al vocabolario (devono essere pochi):

```bash
python3 -c "
vocab=set(l.strip() for l in open('datasets/cs_vocab.txt'))
lines=open('datasets/finetune_cs_full_dp/train_dataset.tsv').readlines()[1:201]
tot=unk=0
for l in lines:
    for t in l.rstrip().split('\t')[-1].split():
        tot+=1; unk+= t not in vocab
print(round(100*unk/tot,2), '% sconosciuti;', tot//len(lines), 'token per riga')"
```
