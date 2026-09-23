#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verifică instalarea ArenaEdit (fără interfață grafică).
Rulează:  python test_core.py

Testează:
  1. operațiile de bază pe imagini (PIL)
  2. catalogul și tiparele de descărcare
  3. motorul AI cap-coadă cu un model minuscul (~2 MB, se descarcă automat):
     generare text→imagine și editare imagine→imagine
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS, FAIL = 0, 0


def check(name, fn):
    global PASS, FAIL
    try:
        fn()
        PASS += 1
        print(f"  [OK]   {name}")
    except Exception as e:
        FAIL += 1
        print(f"  [ESEC] {name} → {e}")
        import traceback
        traceback.print_exc()


def main():
    print("=" * 60)
    print("ArenaEdit — verificare instalare")
    print("=" * 60)

    print("\n1. Module Python de bază…")
    def t_imports():
        import PIL  # noqa
        import customtkinter  # noqa
    check("PIL + customtkinter", t_imports)

    print("\n2. Operații de bază pe imagini…")
    from core import basics
    from PIL import Image

    workdir = tempfile.mkdtemp(prefix="arenaedit_test_")

    def t_basics():
        img = Image.new("RGB", (200, 100), (30, 120, 220))
        img.save(os.path.join(workdir, "src.png"))
        img2 = basics.load_image(os.path.join(workdir, "src.png"))
        assert img2.size == (200, 100)
        r = basics.rotate_image(img2, 90)
        assert r.size == (100, 200), f"rotire 90: {r.size}"
        r = basics.rotate_image(img2, -90)
        assert r.size == (100, 200), f"rotire -90: {r.size}"
        rs = basics.resize_image(img2, 50, 999, keep_ratio=True)
        assert rs.size == (50, 25), f"resize: {rs.size}"
        c = basics.crop_image(img2, (10, 10, 60, 50))
        assert c.size == (50, 40), f"crop: {c.size}"
        e = basics.enhance_image(img2, brightness=1.5, contrast=1.2)
        assert e.size == (200, 100)
        f = basics.flip_image(img2, True)
        assert f.size == (200, 100)
        p = basics.save_image(e, os.path.join(workdir, "out.jpg"), "JPEG", 90)
        assert os.path.exists(p) and p.endswith(".jpg")
        assert basics.fit_size(200, 100, 50, 50) == (50, 25)
    check("încărcare/rotire/resize/crop/ajustări/salvare", t_basics)

    print("\n3. Catalog modele + tipare de descărcare…")
    from core import models

    def t_catalog():
        assert models.find_model("stabilityai/sd-turbo") is not None
        assert models.find_model("timbrooks/instruct-pix2pix").pix2pix
        allow, ignore = models.patterns_for("stabilityai/sd-turbo")
        assert "*.fp16.safetensors" in allow
        assert not models._match("sd_turbo.safetensors", allow), \
            "fișierul-pivot mare nu trebuie descărcat!"
        assert models._match("unet/diffusion_pytorch_model.fp16.safetensors", allow)
        allow2, ignore2 = models.patterns_for("model/necunoscut")
        assert models._match("unet/diffusion_pytorch_model.safetensors", allow2)
        assert not models._match("sd_xl_base_1.0.safetensors", allow2)
        assert models._match("safety_checker/model.safetensors", ignore2)
    check("catalog + tipare fnmatch", t_catalog)

    def t_expected():
        total = models.ModelManager(os.path.join(workdir, "cache")).expected_bytes("stabilityai/sd-turbo")
        assert total and 2.0e9 < total < 3.2e9, f"dimensiune neașteptată: {total}"
        print(f"         (SD Turbo ≈ {total/1e9:.2f} GB — corect)")
    check("dimensiune estimată SD Turbo (prin API Hugging Face)", t_expected)

    print("\n3b. Librărie de prompt-uri predefinite…")
    from core.prompts import PROMPT_LIBRARY, CATEGORIES, search_prompts

    def t_library():
        assert len(PROMPT_LIBRARY) >= 20, f"prea puține: {len(PROMPT_LIBRARY)}"
        ids = [p.id for p in PROMPT_LIBRARY]
        assert len(ids) == len(set(ids)), "id-uri duplicate"
        for p in PROMPT_LIBRARY:
            assert p.titlu and p.prompt and p.categorie, f"câmp gol: {p.id}"
            assert p.target in ("generare", "editare"), f"target invalid: {p.id}"
            if p.target == "editare":
                assert p.mod in ("Instrucțiune", "Reimaginare"), p.id
        gens = [p for p in PROMPT_LIBRARY if p.target == "generare"]
        edits = [p for p in PROMPT_LIBRARY if p.target == "editare"]
        assert gens and edits, "trebuie să existe ambele tipuri"
        assert len(search_prompts("zăpadă")) >= 1
        assert len(search_prompts("", "Peisaje")) >= 1
        assert len(search_prompts("xyzabc_inexistent")) == 0
        print(f"         ({len(PROMPT_LIBRARY)} prompt-uri, {len(CATEGORIES)} categorii)")

    check("librărie de prompt-uri consistentă + căutare", t_library)

    print("\n4. Motorul AI (torch + diffusers, model minuscul de test)…")
    try:
        from core.engine import AIEngine, detect_device
    except Exception as e:
        print(f"  [ESEC] import motor: {e}")
        print("\nRezumat: UNUL SAU MA MULTE TESTE AU EȘUAT.")
        return 1

    dev = detect_device("auto")
    print(f"         dispozitiv detectat: {dev['kind']} — {dev['name']}"
          + (f" ({dev['vram_gb']:.1f} GB VRAM)" if dev.get("vram_gb") else ""))

    eng = AIEngine(os.path.join(workdir, "cache"), "auto")
    tiny = "hf-internal-testing/tiny-stable-diffusion-torch"

    def t_generate():
        eng.load("generate", tiny)
        imgs = eng.generate(prompt="o pisică albastră", steps=2, guidance=1.0,
                            seed=42, width=64, height=64)
        assert imgs and imgs[0].size == (64, 64), f"rezultat: {imgs}"
        imgs[0].save(os.path.join(workdir, "gen_test.png"))
    check("generare text → imagine (model minuscul)", t_generate)

    def t_img2img():
        src = Image.new("RGB", (64, 64), (200, 60, 60))
        eng.load("edit", tiny)
        out = eng.edit_img2img(image=src, prompt="abstract art", steps=3, strength=0.6,
                               guidance=1.0, seed=7)
        assert out is not None and out.size == (64, 64)
    check("editare imagine → imagine (model minuscul)", t_img2img)

    print("\n" + "=" * 60)
    if FAIL == 0:
        print(f"TOATE TESTELE AU TRECUT ({PASS}). Instalarea e funcțională! ✓")
        print("Poți porni aplicația:  python app.py")
        return 0
    print(f"REZULTAT: {PASS} trecute, {FAIL} eșuate.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
