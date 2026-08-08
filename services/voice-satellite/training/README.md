# Hey Velora model training

Kyrion trains the first custom wake-word model locally with openWakeWord. The
runtime artifact is ONNX; TensorFlow and TFLite are intentionally excluded. This
keeps training compatible with the current Linux/Python toolchain and matches the
Raspberry Pi inference path.

## Storage boundary

The dedicated WSL distribution `Kyrion-Voice-Training` is imported at
`E:\Kyrion\Data\voice-training\wsl`. Everything under Linux `/training` therefore
lives on `E:`: Python runtimes, virtual environments, package caches, source
checkouts, datasets, generated audio, checkpoints, and exported models. Large or
generated artifacts must not be committed to this repository.

Expected layout:

```text
/training/
  cache/
  data/
    background/
    openwakeword_features_ACAV100M_2000_hrs_16bit.npy
    validation_set_features.npy
  output/
  src/
    openWakeWord/
    piper-sample-generator-v2.0.0/
  venv/
```

## Pinned upstream inputs

- openWakeWord commit `368c03716d1e92591906a84949bc477f3a834455`
- Piper Sample Generator tag `v2.0.0`, commit
  `195e3bd967d54589c2137c9de2b22ad526ba6b6f`
- Python `3.10.20`
- PyTorch/Torchaudio `2.1.2+cu121`
- NumPy `1.26.4`
- Setuptools `80.9.0` because Piper v2's WebRTC VAD still imports
  `pkg_resources`
- AudioSet `balanced/train` shard `data/bal_train/00.parquet`, distributed as
  CC-BY-4.0 by the dataset host; retain its dataset card and attribution

The source and model licenses must be reviewed together with dataset provenance
before distributing a trained model. A locally trained model is not automatically
safe to publish or use commercially.

The old upstream notebook refers to removed `bal_train09.tar` files. Kyrion uses
the current parquet layout instead. The first verified shard is stored as
`/training/data/audioset-balanced-00.parquet`; its published SHA-256 is
`b433e7bcf3bbdfb0488791fceae1eb7100711d13093d22e2253f15d2dcabc084`.
It contains 500 clips. Install `pyarrow` in `/training/venv` and extract the
bounded background set:

```bash
PYTHON=/training/venv/bin/python
EXTRACT=/mnt/e/dev/Kyrion/kyrion/services/voice-satellite/training/extract_audioset_background.py
$PYTHON "$EXTRACT" /training/data/audioset-balanced-00.parquet /training/data/background --limit 2000
```

## Training stages

Run from the WSL distribution. Copy the tracked configuration into `/training`
or refer to it through `/mnt/e/dev/Kyrion/kyrion`.

```bash
CONFIG=/mnt/e/dev/Kyrion/kyrion/services/voice-satellite/training/hey_velora.yml
PYTHON=/training/venv/bin/python
TRAIN=/training/src/openWakeWord/openwakeword/train.py
RUNNER=/mnt/e/dev/Kyrion/kyrion/services/voice-satellite/training/run_openwakeword_training.py

$PYTHON "$RUNNER" "$TRAIN" --training_config "$CONFIG" --generate_clips
$PYTHON "$RUNNER" "$TRAIN" --training_config "$CONFIG" --augment_clips
$PYTHON "$RUNNER" "$TRAIN" --training_config "$CONFIG" --train_model
```

The runner mixes stereo room impulse responses down to the satellite's mono
capture format and normalizes SpeechBrain's one-element `direct_index` tensor to
the documented integer `rotation_index` argument. Without these narrow
compatibility fixes, current SpeechBrain releases fail while applying room
impulse responses.

The final artifact is `/training/output/hey_velora/hey_velora.onnx`. Do not deploy
it merely because training completed. First record:

1. the exact input checksums and licenses;
2. false accepts per hour on speech, music, and normal room noise;
3. false rejects across distance, volume, orientation, and intended speakers;
4. the selected production threshold;
5. the model checksum and version.

The Pi voice satellite must keep audio local before wake detection. A detection
only opens a bounded audio session; it does not itself authorize commands.
