# ArenaEdit — Studio AI pentru imagini (Windows 11)

**Generează și editează imagini cu inteligență artificială, 100% local, direct din Windows.**
Fără abonamente, fără chei API, fără cloud — modelele rulează pe calculatorul tău și imaginile
nu părăsesc niciodată PC-ul.

---

## Ce știe să facă

| Funcție | Descriere |
|---|---|
| ✦ **Generare** | Creezi imagini noi dintr-o descriere text (română sau engleză) |
| ✎ **Editare AI prin instrucțiuni** | Încarci o imagine și scrii ce vrei să schimbi: *„pune apus de soare"*, *„șterge fundalul"*, *„transformă în desen"* |
| ↻ **Reimaginare** | Imaginea ta + un prompt = variantă nouă (modele SD/SDXL) |
| ⌗ **Editare de bază** | Redimensionare, rotire, oglindire, decupare cu mouse-ul, luminozitate/contrast/saturație/claritate, conversie PNG/JPG/WebP/BMP |
| ⊞ **Istoric** | Toate rezultatele se salvează automat într-un folder (implicit `Imagini\ArenaEdit`) |

Scurtături: **Ctrl+Enter** = generează/editează · **Ctrl+V** = lipește imagine din clipboard · **Ctrl+Z** = undo (la editare de bază).

---

## Cerințe

- **Windows 11** (funcționează și pe 10)
- **Python 3.10 – 3.13** — [descarcă gratuit](https://www.python.org/downloads/)
  ⚠️ La instalare bifează **„Add python.exe to PATH"**.
- **Opțional, dar recomandat:** placă video **NVIDIA cu 6+ GB VRAM** (RTX 2060 sau mai nou).
  Fără NVIDIA aplicația merge pe procesor, dar o imagine durează **1–5 minute** în loc de secunde.
- **Spațiu pe disc:** ~6 GB pentru librării + 2,7–7 GB per model AI descărcat.

---

## Instalare (5–15 minute, o singură dată)

1. Descarci/copiezi întreg folderul **ArenaEdit** pe PC (ex. în `Documente`).
2. Doble-click pe **`INSTALARE.bat`** — creează mediul virtual și instalează librăriile AI (~3–4 GB).
3. La final, aplicația pornește singură. Data următoare o pornești cu **`PORNIRE.bat`**.

**Verificare (opțional):** `python test_core.py` rulează o verificare completă a instalării,
inclusiv un test cap-coadă al motorului AI cu un model minuscul.

## Cum obțin un .exe portabil (opțional)

Dacă vrei o singură aplicație `.exe`, fără să mai ții folderul cu Python:

1. Rulezi întâi `INSTALARE.bat` (o dată).
2. Doble-click pe **`BUILD_EXE.bat`** — după 5–15 minute găsești aplicația în **`dist\ArenaEdit\ArenaEdit.exe`**.
3. Poți copia folderul `dist\ArenaEdit` oriunde (Desktop, stick) — e de sine stătător.

> **Notă Windows Defender:** exe-ul nu e semnat digital, deci la prima pornire Windows poate
> arăta „Windows a protejat computerul". Apasă **„Mai multe informații" → „Rulați oricum"**.

---

## Primii pași în aplicație

1. **Descarcă un model** (o singură dată):
   - la prima pornire apeși butonul **„Descarcă SD Turbo"** (~2,7 GB, recomandat pentru început), sau
   - din tab-ul **Setări → Modele AI**.
   - Modele disponibile:

| Model | Folosit pentru | Descărcare | Observații |
|---|---|---|---|
| **SD Turbo** | Generare | ~2,7 GB | Ultra-rapid (1–4 pași), cel mai bun pentru început |
| **SDXL 1.0** | Generare | ~7 GB | Cea mai bună calitate, 1024px, 8+ GB VRAM |
| **SDXL Turbo** | Generare | ~7 GB | SDXL la viteză mare |
| **InstructPix2Pix** | Editare prin instrucțiuni | ~2,2 GB | „Șterge fundalul", „fă iarnă" etc. |
| orice model Hugging Face | ambele | variază | Setări → „Adaugă orice model difuzie" |

2. **Generare:** tab-ul *Generare* → scrii o descriere → **Generează** (Ctrl+Enter).
3. **Editare AI:** tab-ul *Editare AI* → încarci o imagine (sau Ctrl+V) → alegi modelul
   InstructPix2Pix → scrii instrucțiunea → **Editează imaginea**. Cu **„Continuă de aici ↻"**
   poți aplica mai multe editări unul după altul.
4. **Editare de bază:** tab-ul *Editare de bază* → decupare trasând un dreptunghi cu mouse-ul,
   rotire, redimensionare, ajustări cu slider-ele, apoi **Salvează ca…** în formatul dorit.

---

## Unde se salvează fișierele

- **Imaginile generate/editate:** `Imagini\ArenaEdit` (schimbabil din *Setări*), salvate automat ca PNG.
- **Modelele AI:** folderul `models` de lângă aplicație (poți șterge oricând un model din *Setări*).
- **Setările:** `setari.json` de lângă aplicație.
- Folderul `models` se poate copia între instalații — nu trebuie re-descărcat.

## Rezolvarea problemelor

| Problemă | Soluție |
|---|---|
| „Python nu a fost găsit" | Reinstalează Python cu bifa „Add python.exe to PATH" |
| Generarea e foarte lentă | Nu ai CUDA/NVIDIA. În *Setări* → dispozitiv, ales automat CPU. Poți reduce pașii sau folosi SD Turbo |
| „Memoria plăcii video este insuficientă" | Scad rezoluția la 512×512, folosesc SD Turbo, sau trec pe CPU din Setări |
| Descărcare model întreruptă | Relansează — se reia de unde a rămas (fișierele incomplete se refac automat) |
| Aplicația nu pornește după build | Rulează `dist\ArenaEdit\ArenaEdit.exe` direct din Explorer, nu din arhivă |

## Confidențialitate

Totul e local: prompt-urile și imaginile sunt procesate **doar** de placa video/procesorul tău.
Singura comunicare cu internetul e descărcarea modelelor de pe Hugging Face (poți deconecta
internetul după aceea — aplicația funcționează offline).

## Pentru dezvoltatori

```bash
git clone https://github.com/UTILIZATOR/arenaedit.git
cd arenaedit
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python app.py          # aplicația
python test_core.py    # suita de teste (motor AI cap-coadă, inclusiv CI)
```

Structură: `app.py` (interfața customtkinter) · `core/engine.py` (motorul diffusers) ·
`core/models.py` (catalog + descărcări optimizate fp16) · `core/basics.py` (operații PIL).
Testele rulează automat pe GitHub Actions la fiecare push (`.github/workflows/teste.yml`).

## Licență

[MIT](LICENSE) — poți folosi, modifica și redistribui codul liber, cu păstrarea mențiunii
de copyright. Modelele AI aparțin autorilor lor (Stability AI, timbrooks etc.) și sunt
supuse licențelor proprii de pe Hugging Face.

---

*ArenaEdit v1.0 · autor: **Nitulescu Victor** ([victornitulescu@yahoo.com](mailto:victornitulescu@yahoo.com)) · construit cu [diffusers](https://github.com/huggingface/diffusers), [customtkinter](https://github.com/TomSchimansky/CustomTkinter) și modele [Hugging Face](https://huggingface.co).*
