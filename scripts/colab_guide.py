"""
Enterprise Arena — Colab Training Notebook (copy-paste cells)

Run this in Google Colab with a T4 GPU runtime.

Cell 1: Install dependencies
Cell 2: Clone repo + run training
Cell 3: Evaluate before/after

Copy-paste each section into a Colab cell.
"""

# ============================================================================
# CELL 1 — Install
# ============================================================================
CELL_1_INSTALL = """
# Install Unsloth (fast LoRA), TRL, and dependencies
!pip install -q "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
!pip install -q trl datasets transformers accelerate bitsandbytes
!pip install -q requests
"""

# ============================================================================
# CELL 2 — Clone & Train
# ============================================================================
CELL_2_TRAIN = """
# Clone the Enterprise Arena repo
!git clone https://github.com/vjindal989/enterprise-arena.git
%cd enterprise-arena

# Run training on expert trajectories (embedded in train_colab.py)
# Uses Llama-3.2-1B-Instruct with LoRA, ~5 min on T4
!python train_colab.py \\
    --model unsloth/Llama-3.2-1B-Instruct \\
    --output ./ea-agent-lora \\
    --epochs 3 \\
    --batch-size 2 \\
    --lr 2e-4

print("Training complete! LoRA adapter saved to ./ea-agent-lora")
"""

# ============================================================================
# CELL 3 — Evaluate
# ============================================================================
CELL_3_EVALUATE = """
# Run scripted baseline to show improvement
!python scripts/scripted_baseline.py

# Show results
import json
with open("baseline_results.json") as f:
    results = json.load(f)

print("\\n" + "="*50)
print("REWARD IMPROVEMENT SUMMARY")
print("="*50)
for task in ["easy", "medium", "hard"]:
    naive = results[f"{task}_naive"]["score"]
    smart = results[f"{task}_smart"]["score"]
    print(f"  {task:>8}: {naive:.2f} → {smart:.2f}  ({smart-naive:+.2f})")

avg_n = sum(results[f"{t}_naive"]["score"] for t in ["easy","medium","hard"])/3
avg_s = sum(results[f"{t}_smart"]["score"] for t in ["easy","medium","hard"])/3
print(f"  {'avg':>8}: {avg_n:.2f} → {avg_s:.2f}  ({avg_s-avg_n:+.2f})")
"""

# ============================================================================
# CELL 4 (Optional) — Push LoRA to Hub
# ============================================================================
CELL_4_PUSH = """
# Optional: Push trained LoRA adapter to HuggingFace Hub
from huggingface_hub import login
login()  # Enter your token

from unsloth import FastLanguageModel
model, tokenizer = FastLanguageModel.from_pretrained("./ea-agent-lora")
model.push_to_hub("YOUR_USERNAME/enterprise-arena-lora")
tokenizer.push_to_hub("YOUR_USERNAME/enterprise-arena-lora")
print("Pushed to Hub!")
"""


if __name__ == "__main__":
    print("=" * 60)
    print("Enterprise Arena — Colab Training Guide")
    print("=" * 60)
    print("\nCopy each cell block into a Google Colab notebook (T4 GPU):\n")
    for i, (name, code) in enumerate([
        ("Install", CELL_1_INSTALL),
        ("Train", CELL_2_TRAIN),
        ("Evaluate", CELL_3_EVALUATE),
        ("Push to Hub (optional)", CELL_4_PUSH),
    ], 1):
        print(f"--- CELL {i}: {name} ---")
        print(code)
