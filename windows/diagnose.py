"""Run diagnostics on the Windows computer receiving the portable build."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Desktop"))
from controller import command


def main():
    try:
        import torch
        from ctranslate2 import get_supported_compute_types
        from transformers import (
            Qwen3ASRForConditionalGeneration,
            Qwen3ASRForTokenClassification,
        )

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA ist nicht verfügbar. Prüfe den NVIDIA-Treiber.")
        props = torch.cuda.get_device_properties(0)
        torch.ones(1, device="cuda").add_(1)
        assert Qwen3ASRForConditionalGeneration and Qwen3ASRForTokenClassification
        print(
            f"NVIDIA-GPU: {props.name}\nGrafikspeicher: {props.total_memory / 2**30:.1f} GiB"
        )
        print(f"PyTorch CUDA: {torch.version.cuda}")
        print(
            f"CTranslate2 CUDA: {', '.join(sorted(get_supported_compute_types('cuda')))}"
        )
        command("status")
        print("VoxDrop-Dienst antwortet.")
    except Exception as exc:  # noqa: BLE001 - show native dependency failures
        print(f"Diagnose fehlgeschlagen: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    result = main()
    if sys.stdin.isatty():
        input("\nEnter zum Schließen …")
    raise SystemExit(result)
