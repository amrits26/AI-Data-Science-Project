import torch
import transformers
print(f"torch: {torch.__version__}")
print(f"transformers: {transformers.__version__}")
print(f"cuda available: {torch.cuda.is_available()}")
