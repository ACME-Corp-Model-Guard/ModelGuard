from huggingface_hub import snapshot_download
import tempfile
from typing import List

# Glob patterns to ignore (large binary files)
IGNORE_PATTERNS: List[str] = [
    # PyTorch weights
    "*.bin",
    "pytorch_model*.bin",
    # Safetensors weights
    "*.safetensors",
    "model*.safetensors",
    # Other model formats
    "*.pt",
    "*.pth",
    "*.onnx",
    "*.gguf",
    "*.ggml",
    # TensorFlow/Keras
    "*.h5",
    "tf_model.h5",
    # Flax/JAX
    "*.msgpack",
    "flax_model.msgpack",
    # Large dataset files
    "*.arrow",
    "*.parquet",
]

# Glob patterns to allow (metadata and documentation files)
ALLOW_PATTERNS: List[str] = [
    # Config files
    "*.json",
    "*.yaml",
    "*.yml",
    "*.cfg",
    "*.ini",
    # Documentation
    "*.md",
    "*.txt",
    "*.rst",
    "README*",
    "LICENSE*",
    # Code samples
    "*.py",
]

cache_dir = tempfile.mkdtemp(dir="C:\\Users\\Cody\\Desktop\\testing", prefix="hf_test_")

snapshot_path = snapshot_download(
    repo_id="ILSVRC/imagenet-1k",
    repo_type="dataset",  # "model" or "dataset"
    cache_dir=cache_dir,
    local_dir=cache_dir,
    ignore_patterns=IGNORE_PATTERNS,
    allow_patterns=ALLOW_PATTERNS,
)