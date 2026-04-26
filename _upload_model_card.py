"""One-off script to create HF model repo with model card."""
import os
from huggingface_hub import HfApi

api = HfApi(token=os.environ.get("HF_TOKEN"))

api.create_repo(repo_id="Vjindal26/ea-agent-lora", exist_ok=True, repo_type="model")

model_card = """---
tags:
  - enterprise-arena
  - openenv
  - lora
  - unsloth
  - llama
  - peft
license: mit
base_model: unsloth/Llama-3.2-1B-Instruct
datasets:
  - custom
---

# Enterprise Arena Agent (LoRA)

Fine-tuned **Llama-3.2-1B-Instruct** with LoRA for navigating enterprise workflows under stochastic schema drift, adversarial information sources, and cascading consequences.

## Training Details

| Parameter | Value |
|-----------|-------|
| Base Model | unsloth/Llama-3.2-1B-Instruct |
| Method | LoRA (r=16, alpha=16) |
| Trainable Params | 11.3M (0.90%) |
| Epochs | 3 |
| Training Loss | 2.16 → 1.79 (−17%) |
| Hardware | Google Colab T4 |
| Training Time | ~9 seconds |
| Expert Trajectories | 6 |

## What It Learns

1. **Verify before acting** — always check docs/policy before calling an API
2. **Read error messages** — 404 responses contain migration hints; parse and adapt
3. **Cross-reference adversarial sources** — when manager and policy disagree, trust policy
4. **Handle cascading failures** — resolve tickets before deals to prevent escalation chains
5. **Adapt to drift** — detect schema changes and recover (v1→v2 endpoints, new required fields)

## Usage

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = AutoModelForCausalLM.from_pretrained("unsloth/Llama-3.2-1B-Instruct")
model = PeftModel.from_pretrained(base, "Vjindal26/ea-agent-lora")
tokenizer = AutoTokenizer.from_pretrained("Vjindal26/ea-agent-lora")
```

## Training Script

```bash
pip install unsloth trl datasets transformers accelerate bitsandbytes
python train_colab.py --push-to-hub Vjindal26/ea-agent-lora --hf-token $HF_TOKEN
```

The training script embeds 6 expert trajectories covering:
- Basic deal closure with source verification
- Drift recovery (API rename v1→v2)
- Cascade recovery (ticket escalation handling)
- Trust degradation (manager becomes unreliable)
- Hard task with compliance audit
- Multi-agent auditor consultation

## Results

| Task | Naive | Smart | Improvement |
|------|-------|-------|-------------|
| Easy | 0.61 | 0.94 | +54% |
| Medium | 0.52 | 0.94 | +81% |
| Hard | 0.34 | 0.86 | +153% |
| **Avg** | **0.49** | **0.91** | **+86%** |

## Links

- [Live Demo](https://vjindal26-enterprise-arena.hf.space)
- [Playground](https://vjindal26-enterprise-arena.hf.space/web/)
- [GitHub](https://github.com/vjindal989/enterprise-arena)
- [Blog](https://github.com/vjindal989/enterprise-arena/blob/main/BLOG.md)
"""

api.upload_file(
    path_or_fileobj=model_card.encode(),
    path_in_repo="README.md",
    repo_id="Vjindal26/ea-agent-lora",
    repo_type="model",
)
print("Done - repo created with model card at https://huggingface.co/Vjindal26/ea-agent-lora")
