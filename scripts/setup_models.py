"""Explicit local setup; downloads only model weights/tokenizer, never sends corpus."""
import shutil
import subprocess
from pathlib import Path

from huggingface_hub import hf_hub_download

for model in ('embeddinggemma', 'qwen3:4b'):
    subprocess.run(['ollama', 'pull', model], check=True)
root = Path(__file__).resolve().parents[1]
(root / 'instance').mkdir(exist_ok=True)
path = hf_hub_download('Qwen/Qwen3-4B', 'tokenizer.json', revision='1cfa9a7208912126459214e8b04321603b3df60c', cache_dir=root / 'instance/hf-cache')
shutil.copyfile(path, root / 'instance/tokenizer.json')
print('Local models/tokenizer ready. Start Ollama before importing.')
