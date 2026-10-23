"""Interleaved, repeatable local experiment orchestration."""
from __future__ import annotations

import hashlib
import json
import platform
import random
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .adapter import OllamaAdapter
from .dataset import load_dataset
from .evaluation import score
from .store import connect, save_experiment, save_observation


def run(dataset: Path, db: Path, *, models: list[str], split: str = "test", repetitions: int = 1,
        temperature: float = 0, seed: int = 42, max_output_tokens: int = 128,
        context_tokens: int = 2048, timeout: float = 180, dry_run: bool = False) -> dict:
    if split not in {"development", "calibration", "test"} or len(set(models)) < 2 or repetitions < 1:
        raise ValueError("Choose two distinct installed models, a valid split, and at least one repetition")
    if not 0 <= temperature <= 2 or not 16 <= max_output_tokens <= 1024 or not 256 <= context_tokens <= 32768 or timeout < 5:
        raise ValueError("Invalid generation or timeout setting")
    items, digest = load_dataset(dataset)
    items = [item for item in items if item["split"] == split]
    if not items:
        raise ValueError("Selected split is empty")
    adapter = OllamaAdapter()
    installed = adapter.installed_models()
    missing = [model for model in models if model not in installed]
    if missing:
        raise ValueError(f"Models are not installed locally: {', '.join(missing)}. No automatic pull is allowed.")
    model_meta = []
    for model in models:
        entry = installed[model]
        detail = entry.get("details") or {}
        model_meta.append({"id": model, "digest": entry.get("digest"), "family": detail.get("family"),
                           "parameterSize": detail.get("parameter_size"),
                           "quantization": detail.get("quantization_level"), "downloadBytes": entry.get("size")})
    revision = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False).stdout.strip() or "unknown"
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=False).stdout.strip())
    config = {"temperature": temperature, "seed": seed, "maxOutputTokens": max_output_tokens,
              "contextTokens": context_tokens, "thinking": False, "template": "Ollama model chat template",
              "warmup": "one separate unmeasured chat request per model", "orderSeed": seed,
              "timeoutSeconds": timeout, "retries": 0}
    metadata = {"schemaVersion": 2, "id": f"local-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}",
                "executedAt": datetime.now(timezone.utc).isoformat(), "datasetVersion": "local-v1-frozen-2026-10-23",
                "datasetSha256": digest, "split": split, "runtime": "Ollama", "runtimeVersion": adapter.version(),
                "hardware": {"os": platform.system(), "architecture": platform.machine(),
                             "cpu": platform.processor() or "unavailable", "gpu": "not measured",
                             "memoryBytes": _physical_memory()},
                "generation": config, "repetitions": repetitions, "models": model_meta,
                "codeRevision": revision + ("+dirty" if dirty else ""), "protocol": "one user message; nonstreaming; randomized model order per prompt and repetition",
                "limitations": "Single local host; no TTFT; tokenizers differ; no power or quality judge; small synthetic suite."}
    if dry_run:
        return {"metadata": metadata, "plannedMeasuredCalls": len(items) * repetitions * len(models), "warmupCalls": len(models)}
    with connect(db) as conn:
        save_experiment(conn, metadata)
        for model in models:
            adapter.generate(model, "Reply READY.", temperature=temperature, seed=seed,
                             max_output_tokens=16, context_tokens=context_tokens, timeout=timeout)
        order = [(item, repetition, model) for repetition in range(repetitions) for item in items for model in models]
        random.Random(seed).shuffle(order)
        for index, (item, repetition, model) in enumerate(order):
            identifier = hashlib.sha256(f"{metadata['id']}:{model}:{item['id']}:{repetition}".encode()).hexdigest()[:20]
            try:
                measurement = adapter.generate(model, item["prompt"], temperature=temperature, seed=seed,
                                               max_output_tokens=max_output_tokens,
                                               context_tokens=context_tokens, timeout=timeout)
                error = None
            except Exception as exc:
                measurement = {"response": None, "status": "error", "doneReason": None,
                               "wallMs": None, "ollamaTotalMs": None, "loadMs": None, "promptMs": None,
                               "generationMs": None, "inputTokens": None, "cachedInputTokens": None,
                               "outputTokens": None, "tokensPerSecond": None}
                error = f"{type(exc).__name__}: {str(exc)[:200]}"
            observation = {"id": identifier, "experimentId": metadata["id"], "model": model,
                           "itemId": item["id"], "category": item["category"], "prompt": item["prompt"],
                           "repetition": repetition, **measurement,
                           "evaluation": score(item, measurement["response"]), "error": error}
            save_observation(conn, observation)
            print(json.dumps({"number": index + 1, "of": len(order), "model": model,
                              "item": item["id"], "status": observation["status"]}), flush=True)
    return {"metadata": metadata, "observations": len(order)}


def _physical_memory() -> int | None:
    if platform.system() == "Windows":
        import ctypes
        class Memory(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        value = Memory()
        value.dwLength = ctypes.sizeof(value)
        return value.ullTotalPhys if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)) else None
    if Path("/proc/meminfo").exists():
        first = Path("/proc/meminfo").read_text().splitlines()[0].split()
        return int(first[1]) * 1024
    return None
