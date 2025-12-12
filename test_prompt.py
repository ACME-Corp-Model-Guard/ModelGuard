#!/usr/bin/env python3
"""
Quick test script for iterating on LLM prompts without deployment.
Just generates the prompt text - copy/paste into Claude, ChatGPT, or any LLM.

Usage:
    python test_prompt.py > prompt.txt
"""

import json
from typing import Dict


def build_extract_fields_from_files_prompt(
    fields: Dict[str, str],
    files: Dict[str, str],
) -> str:
    """Construct a structured prompt for extracting fields from files."""

    # Convert list to json, with value = PUT VALUE HERE
    fields_json: Dict[str, Optional[str]] = {}
    for item in fields:
        fields_json[item] = "PUT VALUE HERE"

    instructions = f"""
Your task: Extract specific field values from repository files.

Fields needed: {json.dumps(fields_json)}

IMPORTANT: Repository files are provided below. You MUST read ALL files before responding.
Do NOT generate output until you have examined every file.

Instructions:
1. Read each file completely
2. Identify relevant values for each field
3. Select one value per field (if multiple candidates exist, choose the most relevant)
4. After reading ALL files, generate a JSON response

Output requirements:
- Format: {{ "field_name": "extracted_value" }}
- Include all requested fields that you can find. If you are not confident in a value, use null.
- Use actual values found in the files (not placeholders)

Begin reading the files now:
    """

    sections = [f"=== FILE: {fname} ===\n{content}\n" for fname, content in files.items()]

    return instructions.strip() + "\n\n" + "\n".join(sections)


# Sample files similar to what you see in production
SAMPLE_FILES = {
    "README.md": """---
language: en
tags:
- exbert
license: apache-2.0
datasets:
- bookcorpus
- wikipedia
---

# BERT base model (uncased)

Pretrained model on English language using a masked language modeling (MLM) objective.
This model is uncased: it does not make a difference between english and English.
""",
    "config.json": """{
  "architectures": [
    "BertForMaskedLM"
  ],
  "model_type": "bert",
  "transformers_version": "4.6.0.dev0"
}""",
    "tokenizer_config.json": """{"do_lower_case": true, "model_max_length": 512}""",
}

# Fields to extract (same as production)
FIELDS = {
    "code_name": "Name of the code artifact",
    "dataset_name": "Name of the dataset artifact",
    "parent_model_name": "Name of the parent model",
    "parent_model_source": "File name where you learned parent model name (if any)",
    "parent_model_relationship": "Relationship to the parent model (if any)",
}


if __name__ == "__main__":
    prompt = build_extract_fields_from_files_prompt(
        fields=FIELDS,
        files=SAMPLE_FILES,
    )
    
    print(prompt)
    print("\n" + "=" * 80)
    print(f"Prompt length: {len(prompt)} chars (~{len(prompt) // 3} tokens)")
    print("=" * 80)
