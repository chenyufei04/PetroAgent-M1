"""按照配置训练 Qwen3-8B QLoRA 适配器。

该脚本只提供可审计训练入口，不会自动下载模型或生成训练数据。训练集必须由工程师
审核，避免把当前实验数值、临时价格和约束阈值固化进模型权重。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="训练 PetroAgent Qwen QLoRA 适配器")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "llm" / "qwen3_8b_qlora.yaml")
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    dataset_path = ROOT / config["training"]["dataset"]
    if not dataset_path.is_file():
        raise SystemExit(f"训练集不存在：{dataset_path}；请先生成并完成人工审核。")

    # 训练依赖只在实际微调环境导入，避免污染 PetroAgent 的轻量运行环境。
    try:
        import torch
        from datasets import load_dataset
        from peft import LoraConfig, prepare_model_for_kbit_training
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments
        from trl import SFTTrainer
    except ImportError as exc:
        raise SystemExit("缺少 QLoRA 训练依赖，请在独立 GPU 环境安装 transformers、peft、trl、datasets、bitsandbytes。") from exc

    quant = config["quantization"]
    bits = BitsAndBytesConfig(
        load_in_4bit=quant["bits"] == 4,
        bnb_4bit_quant_type=quant["quant_type"],
        bnb_4bit_use_double_quant=quant["double_quant"],
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    model = AutoModelForCausalLM.from_pretrained(config["base_model"], quantization_config=bits, device_map="auto")
    model = prepare_model_for_kbit_training(model)
    tokenizer = AutoTokenizer.from_pretrained(config["base_model"], use_fast=True)
    lora = config["lora"]
    peft_config = LoraConfig(
        r=lora["rank"], lora_alpha=lora["alpha"], lora_dropout=lora["dropout"],
        target_modules=lora["target_modules"], task_type="CAUSAL_LM",
    )
    training = config["training"]
    arguments = TrainingArguments(
        output_dir=str(ROOT / training["output_dir"]),
        num_train_epochs=training["epochs"], learning_rate=training["learning_rate"],
        per_device_train_batch_size=training["per_device_batch_size"],
        gradient_accumulation_steps=training["gradient_accumulation_steps"],
        bf16=True, logging_steps=10, save_strategy="epoch", seed=training["seed"],
    )
    dataset = load_dataset("json", data_files=str(dataset_path), split="train")
    trainer = SFTTrainer(
        model=model, tokenizer=tokenizer, train_dataset=dataset, peft_config=peft_config,
        args=arguments, max_seq_length=training["max_sequence_length"], dataset_text_field="text",
    )
    trainer.train()
    trainer.save_model(str(ROOT / training["output_dir"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
