"""
Motorul AI — încarcă modelele locale (diffusers) și rulează generarea / editarea.
NOTĂ: modulul importă torch + diffusers (import lent) — se importă leneș din interfață.
"""
from __future__ import annotations

import gc
import platform
import threading
import time

import torch
from diffusers import AutoPipelineForImage2Image, AutoPipelineForText2Image


class CancelledError(RuntimeError):
    """Ridicată intern când utilizatorul anulează o operație."""


class EngineError(RuntimeError):
    """Eroare de nivel motor, cu mesaj prietenos."""


# ------------------------------------------------------------------ dispozitiv

def detect_device(pref: str = "auto") -> dict:
    """Detectează dispozitivul de calcul disponibil."""
    if pref == "cpu":
        return {"kind": "cpu", "name": platform.processor() or "Procesor", "vram_gb": 0.0,
                "pref": pref, "forced": True}
    if torch.cuda.is_available():
        try:
            p = torch.cuda.get_device_properties(0)
            return {"kind": "cuda", "name": p.name, "vram_gb": p.total_memory / 1e9,
                    "pref": pref, "forced": pref == "cuda"}
        except Exception:
            pass
    if pref == "cuda":
        return {"kind": "cpu", "name": platform.processor() or "Procesor", "vram_gb": 0.0,
                "pref": pref, "forced": True,
                "warning": "Nu s-a detectat CUDA — se folosește CPU (foarte lent)."}
    return {"kind": "cpu", "name": platform.processor() or "Procesor", "vram_gb": 0.0,
            "pref": pref, "forced": False}


# ------------------------------------------------------------------ motor

class AIEngine:
    """Reține un singur pipeline încărcat; serializează operațiile cu un lock."""

    def __init__(self, cache_dir: str, device_pref: str = "auto"):
        self.cache_dir = cache_dir
        self.device_pref = device_pref
        self.device = detect_device(device_pref)
        self._pipe = None
        self._loaded_key = None
        self._lock = threading.RLock()
        self.load_log = ""   # ultimul mesaj de încărcare (pentru depanare)

    # ---------------------------------------------------------------- util
    def _dtype(self) -> torch.dtype:
        return torch.float16 if self.device["kind"] == "cuda" else torch.float32

    def pipeline_type(self) -> str:
        """'pix2pix' | 'img2img' | 'text2img' | '' (nepornit)."""
        if self._pipe is None:
            return ""
        n = type(self._pipe).__name__
        if "InstructPix2Pix" in n:
            return "pix2pix"
        if "Image2Image" in n or "Img2Img" in n:
            return "img2img"
        return "text2img"

    def loaded_repo(self) -> str | None:
        if self._loaded_key is None:
            return None
        return self._loaded_key[1]

    # ---------------------------------------------------------------- încărcare
    def unload(self):
        with self._lock:
            if self._pipe is not None:
                self._pipe = None
                self._loaded_key = None
                gc.collect()
                if torch.cuda.is_available():
                    try:
                        torch.cuda.empty_cache()
                    except Exception:
                        pass

    def set_device_pref(self, pref: str):
        with self._lock:
            if pref != self.device_pref:
                self.device_pref = pref
                self.device = detect_device(pref)
                self.unload()

    def load(self, purpose: str, repo_id: str, variant: str | None = None,
             progress=None) -> dict:
        """
        Încarcă pipeline-ul pentru scopul dat ('generate' | 'edit').
        Blocant — se apelează din fir de execuție. Returnează info despre pipeline.
        """
        with self._lock:
            key = (purpose, repo_id, self.device["kind"])
            if self._pipe is not None and self._loaded_key == key:
                return self._info()

            if progress:
                progress(0.05, "Eliberez memoria modelului anterior…")
            self.unload()

            cls = AutoPipelineForText2Image if purpose == "generate" else AutoPipelineForImage2Image
            dtype = self._dtype()
            use_variant = variant if variant == "fp16" else None

            pipe = None
            # 1) cu safety_checker dezactivat + variant fp16
            # 2) fără kwarg-uri safety (SDXL nu le acceptă)
            # 3) fără variant (repo fără fișiere fp16)
            attempts = []
            if use_variant:
                attempts.append(dict(variant=use_variant, safety_checker=None,
                                     requires_safety_checker=False))
                attempts.append(dict(variant=use_variant))
            attempts.append(dict(safety_checker=None, requires_safety_checker=False))
            attempts.append(dict())

            last_err: Exception | None = None
            for i, extra in enumerate(attempts):
                if progress:
                    progress(0.1 + 0.15 * i, f"Se încarcă modelul {repo_id}…")
                try:
                    pipe = cls.from_pretrained(
                        repo_id,
                        cache_dir=self.cache_dir,
                        torch_dtype=dtype,
                        **extra,
                    )
                    break
                except TypeError as e:
                    last_err = e
                    continue
                except Exception as e:
                    msg = str(e)
                    if use_variant and ("fp16" in msg or "variant" in msg.lower()
                                       or "not found" in msg.lower()
                                       or "OSError" in type(e).__name__):
                        last_err = e
                        continue
                    last_err = e
                    raise EngineError(_friendly_load_error(e, repo_id)) from e

            if pipe is None:
                raise EngineError(_friendly_load_error(last_err, repo_id))

            pipe.set_progress_bar_config(disable=True)
            try:
                pipe.enable_attention_slicing()
            except Exception:
                pass

            if self.device["kind"] == "cuda":
                low_vram = self.device.get("vram_gb", 0) < 8.0
                if low_vram:
                    try:
                        pipe.enable_model_cpu_offload()   # economie VRAM, puțin mai lent
                    except Exception:
                        try:
                            pipe.to("cuda")
                        except Exception as e:
                            raise EngineError(
                                "Modelul nu a putut fi încărcat pe placa video "
                                f"({e}). Încearcă din Setări dispozitivul CPU."
                            ) from e
                else:
                    pipe.to("cuda")
            # pe CPU pipeline-ul e deja pe CPU

            self._pipe = pipe
            self._loaded_key = key
            self.load_log = f"{repo_id} → {type(pipe).__name__} @ {self.device['kind']}"
            if progress:
                progress(1.0, "Model încărcat.")
            return self._info()

    def _info(self) -> dict:
        return {
            "repo_id": self.loaded_repo(),
            "type": self.pipeline_type(),
            "device": self.device["kind"],
            "class": type(self._pipe).__name__ if self._pipe else None,
        }

    # ---------------------------------------------------------------- rulare
    def _step_callback(self, steps: int, progress, cancel: threading.Event | None):
        def cb(_pipe, i, _t, kwargs):
            if cancel is not None and cancel.is_set():
                raise CancelledError()
            if progress:
                try:
                    progress((i + 1) / max(1, steps), f"pas {i + 1}/{steps}")
                except Exception:
                    pass
            return kwargs
        return cb

    def _generator(self, seed: int) -> torch.Generator:
        dev = "cuda" if self.device["kind"] == "cuda" else "cpu"
        return torch.Generator(device=dev).manual_seed(int(seed) % (2**31 - 1))

    @staticmethod
    def _preprocess(img, max_side: int = 768):
        """Redimensionează la latura maximă dată și rotunjește la multipli de 8."""
        from PIL import Image
        if img.mode != "RGB":
            img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > max_side:
            scale = max_side / max(w, h)
            w, h = round(w * scale), round(h * scale)
        w = max(8, round(w / 8) * 8)
        h = max(8, round(h / 8) * 8)
        if (w, h) != img.size:
            img = img.resize((w, h), Image.LANCZOS)
        return img

    def generate(self, *, prompt: str, negative: str = "", width: int = 512, height: int = 512,
                 steps: int = 4, guidance: float = 0.0, seed: int | None = None,
                 count: int = 1, progress=None, cancel: threading.Event | None = None) -> list:
        """Generează imagini din text. Returnează list[PIL.Image]."""
        import random
        with self._lock:
            if self._pipe is None:
                raise EngineError("Niciun model de generare încărcat.")
            if seed is None or seed < 0:
                seed = random.randint(0, 2**31 - 1)
            width = max(64, round(width / 8) * 8)
            height = max(64, round(height / 8) * 8)
            kw = dict(
                prompt=[prompt] * max(1, count) if count > 1 else prompt,
                num_inference_steps=max(1, int(steps)),
                guidance_scale=float(guidance),
                generator=self._generator(seed),
                callback_on_step_end=self._step_callback(int(steps), progress, cancel),
            )
            if negative and guidance > 0.1:
                kw["negative_prompt"] = [negative] * max(1, count) if count > 1 else negative
            if type(self._pipe).__name__.startswith("StableDiffusionXL"):
                kw.update(width=width, height=height)
            else:
                kw.update(width=width, height=height)
            try:
                res = self._pipe(**kw)
                return res.images
            except CancelledError:
                return []
            except torch.cuda.OutOfMemoryError as e:
                raise EngineError(
                    "Memoria plăcii video este insuficientă. Încearcă o rezoluție mai "
                    "mică (512×512) sau din Setări activează dispozitivul CPU."
                ) from e

    def edit_pix2pix(self, *, image, instruction: str, steps: int = 25,
                     image_guidance: float = 1.5, guidance: float = 7.5,
                     seed: int | None = None, progress=None,
                     cancel: threading.Event | None = None):
        """Editare prin instrucțiuni (InstructPix2Pix). Returnează PIL.Image sau None."""
        import random
        with self._lock:
            if "InstructPix2Pix" not in type(self._pipe).__name__:
                raise EngineError(
                    "Modelul încărcat nu suportă editare prin instrucțiuni. "
                    "Alege modelul InstructPix2Pix din listă."
                )
            if seed is None or seed < 0:
                seed = random.randint(0, 2**31 - 1)
            img = self._preprocess(image, max_side=768)
            try:
                res = self._pipe(
                    prompt=instruction,
                    image=img,
                    num_inference_steps=max(1, int(steps)),
                    image_guidance_scale=float(image_guidance),
                    guidance_scale=float(guidance),
                    generator=self._generator(seed),
                    callback_on_step_end=self._step_callback(int(steps), progress, cancel),
                )
                return res.images[0] if res.images else None
            except CancelledError:
                return None
            except torch.cuda.OutOfMemoryError as e:
                raise EngineError(_oom_msg()) from e

    def edit_img2img(self, *, image, prompt: str, negative: str = "", strength: float = 0.7,
                     steps: int = 30, guidance: float = 7.5, seed: int | None = None,
                     progress=None, cancel: threading.Event | None = None):
        """Reimaginare: imaginea sursă + prompt → imagine nouă. Returnează PIL.Image sau None."""
        import random
        with self._lock:
            if self._pipe is None:
                raise EngineError("Niciun model de editare încărcat.")
            if seed is None or seed < 0:
                seed = random.randint(0, 2**31 - 1)
            img = self._preprocess(image, max_side=768)
            steps = max(2, int(steps))
            kw = dict(
                prompt=prompt,
                image=img,
                strength=max(0.05, min(1.0, float(strength))),
                num_inference_steps=steps,
                guidance_scale=float(guidance),
                generator=self._generator(seed),
                callback_on_step_end=self._step_callback(steps, progress, cancel),
            )
            if negative and guidance > 0.1:
                kw["negative_prompt"] = negative
            try:
                res = self._pipe(**kw)
                return res.images[0] if res.images else None
            except CancelledError:
                return None
            except torch.cuda.OutOfMemoryError as e:
                raise EngineError(_oom_msg()) from e


def _oom_msg() -> str:
    return ("Memoria plăcii video este insuficientă pentru această imagine. "
            "Folosește o imagine sursă mai mică sau activează CPU din Setări "
            "(mai lent, dar fără limite de memorie).")


def _friendly_load_error(e: Exception, repo_id: str) -> str:
    msg = str(e)
    if "Connection" in msg or "offline" in msg.lower() or "timed out" in msg.lower():
        return (f"Nu am putut descărca modelul {repo_id} — verifică conexiunea la "
                "internet și încearcă din nou.")
    if "401" in msg or "403" in msg or "gated" in msg.lower():
        return (f"Modelul {repo_id} este privat sau restricționat și nu poate fi "
                "descărcat fără un token Hugging Face.")
    if "No such file" in msg or "not found" in msg.lower() or "does not exist" in msg.lower():
        return (f"Modelul {repo_id} nu a fost găsit pe Hugging Face. Verifică "
                "identificatorul (ex.: 'stabilityai/sd-turbo').")
    return f"Eroare la încărcarea modelului {repo_id}: {msg[:400]}"
