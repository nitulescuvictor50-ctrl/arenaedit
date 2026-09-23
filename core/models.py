"""
Catalogul de modele AI + managerul de descărcare de pe Hugging Face.
Descarcă DOAR fișierele necesare (variante fp16, fără safety-checker,
fără checkpoint-uri unice / ONNX / Flax), reducând drastic volumul.
"""
from __future__ import annotations

import fnmatch
import os
import shutil
import threading
import time
from dataclasses import dataclass, field


@dataclass
class ModelInfo:
    repo_id: str
    name: str
    purpose: str            # "generate" | "edit"
    variant: str | None     # "fp16" dacă există varianta fp16 completă
    pix2pix: bool = False   # suportă editare prin instrucțiuni
    turbo: bool = False     # model distilat (1–4 pași)
    approx_gb: float = 0.0
    desc: str = ""


CATALOG: list[ModelInfo] = [
    ModelInfo(
        repo_id="stabilityai/sd-turbo",
        name="SD Turbo",
        purpose="generate",
        variant="fp16",
        turbo=True,
        approx_gb=2.7,
        desc="Generare ultra-rapidă (1–4 pași, ~2 sec./imagine pe GPU). "
             "Cel mai bun punct de plecare — descărcare mică.",
    ),
    ModelInfo(
        repo_id="stabilityai/stable-diffusion-xl-base-1.0",
        name="SDXL 1.0",
        purpose="generate",
        variant="fp16",
        approx_gb=7.1,
        desc="Cea mai bună calitate, 1024px. Necesită placă video cu 8+ GB VRAM "
             "(sau pornește cu descărcare de memorie).",
    ),
    ModelInfo(
        repo_id="stabilityai/sdxl-turbo",
        name="SDXL Turbo",
        purpose="generate",
        variant="fp16",
        turbo=True,
        approx_gb=7.0,
        desc="SDXL la viteză mare (1–4 pași), 512px.",
    ),
    ModelInfo(
        repo_id="timbrooks/instruct-pix2pix",
        name="InstructPix2Pix",
        purpose="edit",
        variant="fp16",
        pix2pix=True,
        approx_gb=2.2,
        desc="Editare prin instrucțiuni în limbaj natural: „pune apus de soare”, "
             "„șterge persoana din fundal” etc.",
    ),
]


def find_model(repo_id: str) -> ModelInfo | None:
    for m in CATALOG:
        if m.repo_id == repo_id:
            return m
    return None


def get_models(purpose: str) -> list[ModelInfo]:
    return [m for m in CATALOG if m.purpose == purpose]


# ------------------------------------------------------------------ tipare de descărcare

ALLOW_FP16 = ["*.json", "*.txt", "*.model", "*.fp16.safetensors"]
ALLOW_GENERIC = ["*.json", "*.txt", "*.model", "*/*.safetensors", "*/*.bin"]
IGNORE_GENERIC = ["*.ckpt", "*.onnx", "*.onnx_data", "*.msgpack", "*.png", "*.jpg",
                  "*.md", "safety_checker/*", "*.fp16.safetensors", "*.fp16.bin"]


def patterns_for(repo_id: str) -> tuple[list[str], list[str]]:
    """Returnează (allow_patterns, ignore_patterns) pentru snapshot_download."""
    m = find_model(repo_id)
    if m is not None and m.variant == "fp16":
        return ALLOW_FP16, ["safety_checker/*"]
    return ALLOW_GENERIC, IGNORE_GENERIC


def _match(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, p) for p in patterns)


# ------------------------------------------------------------------ interogare Hugging Face

def _list_repo_files(repo_id: str) -> list[tuple[str, int]]:
    """[(cale, bytes)] pentru fișierele din repo, prin API-ul Hugging Face."""
    from huggingface_hub import HfApi
    api = HfApi()
    out: list[tuple[str, int]] = []
    for item in api.list_repo_tree(repo_id, repo_type="model", recursive=True):
        if hasattr(item, "size") and item.size is not None:
            out.append((item.path, item.size))
    return out


class ModelManager:
    """Gestionează descărcarea / ștergerea / verificarea modelelor în cache-ul local."""

    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self._busy = False
        self._lock = threading.Lock()
        self._expected_cache: dict[str, int] = {}
        self._files_cache: dict[str, list[tuple[str, int]]] = {}

    # -- căi helper ------------------------------------------------------
    def _repo_dir(self, repo_id: str) -> str:
        return os.path.join(self.cache_dir, "models--" + repo_id.replace("/", "--"))

    def snapshot_path(self, repo_id: str) -> str | None:
        """Calea snapshot-ului complet (conține model_index.json) sau None."""
        base = self._repo_dir(repo_id)
        snap = os.path.join(base, "snapshots")
        if not os.path.isdir(snap):
            return None
        for name in sorted(os.listdir(snap)):
            d = os.path.join(snap, name)
            if os.path.isfile(os.path.join(d, "model_index.json")):
                return d
        return None

    def is_installed(self, repo_id: str) -> bool:
        return self.snapshot_path(repo_id) is not None

    def installed_bytes(self, repo_id: str) -> int:
        return _dir_size(self._repo_dir(repo_id))

    # -- dimensiuni estimate ---------------------------------------------
    def expected_bytes(self, repo_id: str) -> int | None:
        """Totalul estimat de descărcat pentru fișierele permise (poate fi None la eroare rețea)."""
        if repo_id in self._expected_cache:
            return self._expected_cache[repo_id]
        try:
            allow, ignore = patterns_for(repo_id)
            files = self._list_files(repo_id)
            total = sum(sz for p, sz in files
                        if _match(p, allow) and not _match(p, ignore))
            self._expected_cache[repo_id] = total
            return total
        except Exception:
            return None

    def _list_files(self, repo_id: str) -> list[tuple[str, int]]:
        if repo_id not in self._files_cache:
            self._files_cache[repo_id] = _list_repo_files(repo_id)
        return self._files_cache[repo_id]

    def expected_files(self, repo_id: str) -> int:
        try:
            allow, ignore = patterns_for(repo_id)
            return sum(1 for p, _ in self._list_files(repo_id)
                       if _match(p, allow) and not _match(p, ignore))
        except Exception:
            return 0

    # -- ștergere ----------------------------------------------------------
    def delete(self, repo_id: str) -> bool:
        base = self._repo_dir(repo_id)
        if os.path.isdir(base):
            shutil.rmtree(base, ignore_errors=True)
            return True
        return False

    # -- descărcare --------------------------------------------------------
    @property
    def busy(self) -> bool:
        return self._busy

    def start_download(self, repo_id: str,
                       on_progress=None,   # (done_bytes, total_bytes|None)
                       on_done=None) -> bool:  # (ok: bool, error: str|None)
        """Pornește descărcarea într-un fir de execuție. False dacă deja e una activă."""
        with self._lock:
            if self._busy:
                return False
            self._busy = True

        def run():
            ok, err = True, None
            try:
                from huggingface_hub import snapshot_download
                allow, ignore = patterns_for(repo_id)
                stop_monitor = threading.Event()

                def monitor():
                    total = self.expected_bytes(repo_id)
                    while not stop_monitor.is_set():
                        done = _dir_size(self._repo_dir(repo_id))
                        if on_progress:
                            try:
                                on_progress(done, total)
                            except Exception:
                                pass
                        stop_monitor.wait(0.6)

                mon = threading.Thread(target=monitor, daemon=True)
                mon.start()
                try:
                    snapshot_download(
                        repo_id=repo_id,
                        cache_dir=self.cache_dir,
                        allow_patterns=allow,
                        ignore_patterns=ignore,
                        max_workers=4,
                    )
                finally:
                    stop_monitor.set()
                    mon.join(timeout=2)
                if on_progress:
                    total = self.expected_bytes(repo_id)
                    on_progress(total or _dir_size(self._repo_dir(repo_id)), total)
            except Exception as e:  # noqa: BLE001
                ok, err = False, f"{e}"
            finally:
                with self._lock:
                    self._busy = False
                if on_done:
                    try:
                        on_done(ok, err)
                    except Exception:
                        pass

        threading.Thread(target=run, daemon=True, name=f"dl-{repo_id}").start()
        return True


def _dir_size(path: str) -> int:
    total = 0
    if not os.path.isdir(path):
        return 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def human_gb(n: float) -> str:
    return f"{n / 1e9:.1f} GB" if n >= 1e9 else f"{n / 1e6:.0f} MB"
