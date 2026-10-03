# Pipeline completa

Sequenza dei passi per riprodurre gli esperimenti, per ciascun braccio (`full`, `headeronly`, `payloadonly`). I percorsi negli script di lancio vanno adattati al proprio ambiente.

## 0. Prerequisiti

Repository ufficiale di ET-BERT, con le modifiche di compatibilità di `PATCH_ET-BERT.md`; ambiente virtuale con le dipendenze di `requirements.txt`; `tshark` nel `PATH` (usato da `data_process`).

```bash
cd ~/ET-BERT-main
source etbert_env/bin/activate
export PYTHONPATH=$HOME/ET-BERT-main
```

## 1. Divisione in flussi (solo Cross-Platform)

I PCAP originali di Cross-Platform vengono divisi in un file per flusso con SplitCap. CipherSpectrum è già distribuito con un file per sessione.

## 2. Ablazione

```bash
python3 ablate_pcap.py --keep-payload  PCAP_DIR  OUT_full
python3 ablate_pcap.py                 PCAP_DIR  OUT_headeronly
python3 ablate_pcap.py --payload-only  PCAP_DIR  OUT_payloadonly
```

Nell'output `Intatti` deve essere 0: altrimenti alcuni pacchetti non sono stati interpretati e quindi non modificati.

## 3. Normalizzazione del link layer (solo Cross-Platform)

I PCAP di Cross-Platform sono raw IP. Il preprocessing di ET-BERT scarta i primi 38 byte di ogni pacchetto, che su Ethernet sono Ethernet + IP + porte; per trattare i due dataset allo stesso modo si aggiunge un header Ethernet con MAC a zero:

```bash
python3 normalize_link.py OUT_full         OUT_full_eth
python3 normalize_link.py OUT_headeronly   OUT_headeronly_eth
python3 normalize_link.py OUT_payloadonly  OUT_payloadonly_eth
```

## 4. Selezione delle classi (solo Cross-Platform)

```bash
python3 filter_valid_cp.py
```

Tiene solo i flussi con almeno 3 pacchetti (gli altri sono scartati comunque da ET-BERT) ed esclude le app con meno di 10 flussi validi. La selezione è fatta sul braccio full e applicata identica agli altri due. Sono state inoltre escluse 3 app per cui il preprocessing di ET-BERT lasciava meno di 2 campioni (`com.tilzmatictech.mobile.navigation.delhimetronavigator`, `com.msm.lhmsappolice`, `dev.gautam.bbkiwines`). Classi finali: 202.

## 5. Corpus di pre-training

Con `vocab_process/main.py` di ET-BERT, lanciato da `gen_corpus_cs_*.py` (CipherSpectrum) o `gen_corpus_cp.py` (Cross-Platform), che impostano solo i percorsi. Il vocabolario contiene tutte le 65.536 coppie di byte più i 5 token speciali ed è condiviso da tutti i bracci.

## 6. Dataset di pre-training

Ogni braccio in una cartella temporanea propria, per evitare collisioni dei file `dataset-tmp-*.pt`:

```bash
mkdir -p tmp_preprocess_ARM && cd tmp_preprocess_ARM
python3 -u ../preprocess.py \
  --corpus_path  ../datasets/BURST_ARM.txt \
  --vocab_path   ../datasets/cs_vocab.txt \
  --dataset_path ../datasets/PRETRAIN_ARM.pt \
  --seq_length 512 --processes_num 16 --target bert
```

## 7. Pre-training

Stesso numero di step per tutti i bracci (150.000):

```bash
CUDA_VISIBLE_DEVICES=N python3 -u pre-training/pretrain.py \
  --dataset_path datasets/PRETRAIN_ARM.pt \
  --vocab_path   datasets/cs_vocab.txt \
  --config_path  models/bert_base_config.json \
  --output_model_path models/PRETRAINED_ARM.bin \
  --total_steps 150000 --save_checkpoint_steps 5000 --report_steps 500 \
  --batch_size 32 --embedding word_pos_seg --encoder transformer \
  --mask fully_visible --target bert --world_size 1 --gpu_ranks 0
```

Per riprendere un pre-training interrotto si aggiunge `--pretrained_model_path` con l'ultimo checkpoint.

## 8. Dati di fine-tuning

Con `data_process/main.py` di ET-BERT, lanciato da `run_data_process_cs.py` o `run_data_process_cp.py`, che impostano:

- `dataset_level = "flow"`: primi 5 pacchetti per flusso;
- numero di classi (41 o 202);
- campioni per classe: 500 su CipherSpectrum; su Cross-Platform 500 o tutti i disponibili se meno.

Divisione train/valid/test 80/10/10.

**Allineamento dei flussi (solo Cross-Platform, braccio payload-only).** Il `data_process` scarta flussi diversi quando gli header sono azzerati. Per usare gli stessi flussi in tutti i bracci:

```bash
python3 check_eligible_cp.py            # flussi accettati nel braccio full
python3 run_data_process_cp_matched.py  # TSV del payload-only su quei flussi, stessi campioni per classe del full
```

## 9. Fine-tuning

```bash
CUDA_VISIBLE_DEVICES=N python3 -u fine-tuning/run_classifier.py \
  --pretrained_model_path models/PRETRAINED_ARM.bin-150000 \
  --vocab_path   datasets/cs_vocab.txt \
  --config_path  models/bert_base_config.json \
  --train_path   datasets/FINETUNE_ARM/train_dataset.tsv \
  --dev_path     datasets/FINETUNE_ARM/valid_dataset.tsv \
  --test_path    datasets/FINETUNE_ARM/test_dataset.tsv \
  --output_model_path models/FINETUNED_ARM.bin \
  --epochs_num 50 --batch_size 32 --seq_length 512 --learning_rate 6e-5 \
  --embedding word_pos_seg --encoder transformer --mask fully_visible \
  --report_steps 100
```

## Verifiche consigliate

Un'ablazione può fallire senza errori: prima di un pre-training lungo conviene controllare i byte dei PCAP prodotti e i byte che arrivano al modello, ricostruiti dai TSV.

Token sconosciuti nei TSV rispetto al vocabolario (devono essere pochi):

```bash
python3 -c "
vocab=set(l.strip() for l in open('datasets/cs_vocab.txt'))
lines=open('datasets/FINETUNE_ARM/train_dataset.tsv').readlines()[1:201]
tot=unk=0
for l in lines:
    for t in l.rstrip().split('\t')[-1].split():
        tot+=1; unk+= t not in vocab
print(round(100*unk/tot,2), '% sconosciuti;', tot//len(lines), 'token per riga')"
```
