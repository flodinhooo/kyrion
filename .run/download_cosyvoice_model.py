from huggingface_hub import snapshot_download

snapshot_download(
    "FunAudioLLM/Fun-CosyVoice3-0.5B-2512",
    local_dir="/training/models/cosyvoice3-0.5b-2512",
)
