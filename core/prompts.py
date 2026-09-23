#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArenaEdit — librărie de prompt-uri predefinite.

Fiecare prompt are titlu, descriere și categorie în ROMÂNĂ (ce vede utilizatorul),
iar câmpul `prompt` este optimizat în ENGLEZĂ — modelele Stable Diffusion și
InstructPix2Pix dau rezultate mult mai bune cu prompt-uri în engleză.

Structură înregistrare:
    id         — identificator unic (slug)
    titlu      — nume scurt afișat (română)
    categorie  — grupare în interfață
    descriere  — explicație pentru utilizator (română)
    prompt     — textul efectiv trimis modelului (engleză, stil cuvinte-cheie)
    negativ    — prompt negativ (opțional; folosit când CFG > 0)
    target     — "generare" (text → imagine) sau "editare" (imagine → imagine)
    mod        — pentru target="editare": "Instrucțiune" sau "Reimaginare"
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Prompt:
    id: str
    titlu: str
    categorie: str
    descriere: str
    prompt: str
    negativ: str = ""
    target: str = "generare"
    mod: str = ""


NEG_STANDARD = ("blurry, low quality, deformed, ugly, text, watermark, "
                "duplicate, extra limbs, bad anatomy")

PROMPT_LIBRARY: tuple[Prompt, ...] = (
    # ------------------------------------------------------------- Peisaje
    Prompt("peisaj-aurora", "Aurora boreală peste lac", "Peisaje",
           "Cer nordic spectaculos, reflectat într-un lac de munte.",
           "a stunning aurora borealis over a calm mountain lake, vivid green and purple "
           "lights reflected in the water, snow capped peaks, starry night sky, "
           "ultra detailed, cinematic",
           NEG_STANDARD, "generare"),
    Prompt("peisaj-apus-plaja", "Apus pe plajă tropicală", "Peisaje",
           "Soarele care apune peste ocean, palmieri și nisip cald.",
           "golden sunset over a tropical beach, warm orange and pink sky, gentle waves on "
           "white sand, palm trees silhouetted, soft warm light, photorealistic, high detail",
           NEG_STANDARD, "generare"),
    Prompt("peisaj-padure-cetoasa", "Pădure în ceață, în zori", "Peisaje",
           "Raze de soare prin ceață, atmosferă liniștitoare.",
           "a misty pine forest at dawn, god rays through the fog, mossy ground, moody "
           "atmosphere, cinematic lighting, photorealistic, high detail",
           NEG_STANDARD, "generare"),
    Prompt("peisaj-munte-zapada", "Munte înzăpezit la apus", "Peisaje",
           "Vârf acoperit de zăpadă, lumină de seară.",
           "a majestic snow capped mountain peak at golden hour, dramatic clouds, alpine "
           "meadow with wildflowers in foreground, crisp air, photorealistic, high detail",
           NEG_STANDARD, "generare"),
    Prompt("peisaj-lavanda", "Câmp de lavandă", "Peisaje",
           "Rânduri de lavandă până la orizont, ceață mov.",
           "endless rows of blooming lavender fields at sunset, a lone tree on the horizon, "
           "purple haze, soft warm light, photorealistic",
           NEG_STANDARD, "generare"),
    Prompt("peisaj-oras-noapte", "Oraș ploios, noaptea", "Peisaje",
           "Stradă urbană cu neoane reflectate în asfaltul ud.",
           "a rainy city street at night, neon signs reflecting on wet asphalt, cinematic "
           "cyberpunk mood, shallow depth of field, photorealistic",
           NEG_STANDARD, "generare"),

    # ------------------------------------------------------- Natură & animale
    Prompt("natura-leu", "Leu pe stâncă, la apus", "Natură & animale",
           "Portret de leu sălbatic, cu coama lucind în soare.",
           "a majestic male lion resting on a rock at sunset, golden mane glowing, savanna "
           "background, wildlife photography, telephoto lens, high detail",
           NEG_STANDARD, "generare"),
    Prompt("natura-pisica", "Portret de pisică", "Natură & animale",
           "Pisică pufoasă, ochi verzi, fundal blurat de studio.",
           "a fluffy ginger cat portrait, curious green eyes, studio lighting, soft bokeh "
           "background, ultra sharp, cute",
           NEG_STANDARD, "generare"),
    Prompt("natura-colibri", "Colibri lângă floare", "Natură & animale",
           "Macro cu pasăre colibri în zbor, pene iridescente.",
           "a hummingbird hovering near a bright flower, frozen motion, macro photography, "
           "iridescent feathers, colorful, high detail",
           NEG_STANDARD, "generare"),
    Prompt("natura-cal", "Cal alb în galop", "Natură & animale",
           "Cal sălbatic alergând prin apă, stropi și lumină dramatică.",
           "a wild white horse galloping through shallow water, splashing, dramatic morning "
           "light, motion blur, photorealistic",
           NEG_STANDARD, "generare"),

    # -------------------------------------------------------- Portret & oameni
    Prompt("portret-studio", "Portret de studio", "Portret & oameni",
           "Portret profesional, lumină soft, fundal neutru.",
           "a professional studio portrait of a woman, soft key light, neutral gray "
           "background, sharp focus on the eyes, 85mm lens, high fashion photography",
           NEG_STANDARD, "generare"),
    Prompt("portret-cowboy", "Portret de cowboy", "Portret & oameni",
           "Cowboy cu pălărie, lumină de contur, fundal prăfuit.",
           "a weathered cowboy portrait, wide brim hat, dramatic rim light, dusty western "
           "backdrop, cinematic, photorealistic",
           NEG_STANDARD, "generare"),
    Prompt("portret-regal", "Portret regal baroc", "Portret & oameni",
           "Portret în stilul picturii clasice, coroană și catifea.",
           "a royal portrait in opulent baroque style, golden crown, rich velvet and gold "
           "drapery, dramatic lighting, oil painting, highly detailed",
           NEG_STANDARD, "generare"),
    Prompt("portret-balerina", "Balerină în mișcare", "Portret & oameni",
           "Dansatoare elegantă, lumină de fereastră, tutu fluid.",
           "a graceful ballerina mid dance, elegant pose, soft window light, flowing tutu, "
           "artistic photography, high detail",
           NEG_STANDARD, "generare"),
    Prompt("portret-explorator", "Explorator cu hartă", "Portret & oameni",
           "Portret vechi de aventurier, lumină caldă de lanternă.",
           "an old explorer portrait, vintage map and compass in hand, warm lantern light, "
           "adventurous mood, photorealistic",
           NEG_STANDARD, "generare"),

    # -------------------------------------------------------- Artistic & stiluri
    Prompt("stil-acuarela", "Stil acuarelă", "Artistic & stiluri",
           "Pictură în acuarelă, tușe moi, textură de hârtie.",
           "a delicate watercolor painting, soft washes, paper texture, gentle color "
           "transitions, artistic",
           NEG_STANDARD, "generare"),
    Prompt("stil-ulei", "Stil ulei impresionist", "Artistic & stiluri",
           "Ulei cu tușe groase și culori vibrante.",
           "an impressionist oil painting, visible thick brush strokes, dappled sunlight, "
           "vibrant colors, textured canvas",
           NEG_STANDARD, "generare"),
    Prompt("stil-carbune", "Desen în cărbune", "Artistic & stiluri",
           "Schiță monocromă, umbre dramatice.",
           "a charcoal sketch drawing, expressive strokes, dramatic shadows, on textured "
           "paper, monochrome",
           NEG_STANDARD, "generare"),
    Prompt("stil-anime", "Stil anime", "Artistic & stiluri",
           "Ilustrație anime, linii clare și culori vii.",
           "anime style illustration, big expressive eyes, cel shading, clean lines, vibrant "
           "colors, dynamic composition",
           NEG_STANDARD, "generare"),
    Prompt("stil-digital", "Artă digitală fantasy", "Artistic & stiluri",
           "Ilustrație digitală detaliată, concept art.",
           "a vibrant digital fantasy illustration, highly detailed, dramatic lighting, epic "
           "composition, concept art",
           NEG_STANDARD, "generare"),
    Prompt("stil-cyberpunk", "Stil cyberpunk", "Artistic & stiluri",
           "Neoane, holograme și atmosferă futuristă.",
           "cyberpunk neon style, glowing holograms, rain, purple and teal palette, "
           "futuristic, highly detailed digital art",
           NEG_STANDARD, "generare"),

    # ----------------------------------------------------------- Fantezie & SF
    Prompt("fantezie-castel", "Castel cu dragon", "Fantezie & SF",
           "Castel pe stâncă, dragon pe cer, furtună.",
           "an ancient castle on a cliff, a dragon flying in the sky, stormy clouds, epic "
           "fantasy art, dramatic lighting, highly detailed",
           NEG_STANDARD, "generare"),
    Prompt("fantezie-insule", "Insule plutitoare", "Fantezie & SF",
           "Insule în cer cu cascade care curg în nori.",
           "floating islands in the sky with waterfalls falling into clouds, fantasy "
           "landscape, epic scale, vibrant colors, concept art",
           NEG_STANDARD, "generare"),
    Prompt("fantezie-dragon", "Dragon care suflă foc", "Fantezie & SF",
           "Dragon cu flăcări, peșteră cu comori.",
           "a fire breathing dragon, glowing embers, cavernous lair with treasure, epic "
           "fantasy art, dramatic cinematic lighting",
           NEG_STANDARD, "generare"),
    Prompt("fantezie-robot", "Robot prietenos", "Fantezie & SF",
           "Robot sci-fi cu detalii mecanice, randare 3D.",
           "a friendly sci fi robot, intricate mechanical details, soft studio lighting, "
           "3D render style, high detail",
           NEG_STANDARD, "generare"),
    Prompt("fantezie-elf", "Pădure elfică magică", "Fantezie & SF",
           "Portal luminos între copaci străvechi.",
           "an elven forest with a glowing magical portal, fireflies, ancient trees, mystical "
           "blue light, fantasy art, detailed",
           NEG_STANDARD, "generare"),

    # --------------------------------------------------- Arhitectură & interioare
    Prompt("arh-living", "Living modern", "Arhitectură & interioare",
           "Cameră de zi minimalistă, lemn cald și lumină naturală.",
           "a modern minimalist living room, warm wood and neutral tones, large windows with "
           "natural light, interior design photography, photorealistic",
           NEG_STANDARD, "generare"),
    Prompt("arh-casa", "Casă de vis la amurg", "Arhitectură & interioare",
           "Casă modernă cu geamuri mari și piscină.",
           "a modern dream house exterior at dusk, warm interior lights glowing, large glass "
           "walls, pool, architectural photography",
           NEG_STANDARD, "generare"),
    Prompt("arh-biblioteca", "Bibliotecă veche", "Arhitectură & interioare",
           "Rafturi înalte de cărți, lămpi calde, atmosferă.",
           "a grand old library with towering bookshelves, warm lamps, leather armchairs, "
           "dust motes in light rays, atmospheric, photorealistic",
           NEG_STANDARD, "generare"),
    Prompt("arh-bucatarie", "Bucătărie scandinavă", "Arhitectură & interioare",
           "Bucătărie luminoasă, alb și stejar, plante.",
           "a cozy scandinavian kitchen, white cabinets and oak details, morning sunlight, "
           "green plants, interior photography, photorealistic",
           NEG_STANDARD, "generare"),

    # ---------------------------------------------------------- Obiecte & design
    Prompt("obiect-ceas", "Ceas de lux — macro", "Obiecte & design",
           "Fotografie de produs premium, reflexii și detalii fine.",
           "a luxury wristwatch on dark stone, macro product photography, dramatic studio "
           "lighting, reflections, ultra sharp, premium",
           NEG_STANDARD, "generare"),
    Prompt("obiect-burger", "Burger gourmet", "Obiecte & design",
           "Food photography apetisant, abur și contrast.",
           "a gourmet burger with melting cheese, fresh ingredients, dark moody food "
           "photography, steam, appetizing, high detail",
           NEG_STANDARD, "generare"),
    Prompt("obiect-masina", "Mașină conceptuală", "Obiecte & design",
           "Mașină futuristă, vopsea glossy, randare 3D.",
           "a futuristic concept car, aerodynamic design, glossy paint, studio environment, "
           "3D render, dramatic lighting",
           NEG_STANDARD, "generare"),

    # ------------------------------------------------------ Editare · instrucțiuni
    Prompt("edit-fundal-apus", "Schimbă fundalul în apus", "Editare · instrucțiuni",
           "Înlocuiește fundalul cu un apus cald pe plajă.",
           "change the background to a golden sunset on the beach",
           "", "editare", "Instrucțiune"),
    Prompt("edit-sterge-fundal", "Șterge fundalul", "Editare · instrucțiuni",
           "Scoate fundalul și păstrează subiectul pe fond alb.",
           "remove the background and put the subject on a plain white background",
           "", "editare", "Instrucțiune"),
    Prompt("edit-iarna", "Fă-o iarnă", "Editare · instrucțiuni",
           "Transformă scena în peisaj de iarnă, cu zăpadă.",
           "turn the scene into winter, add snow everywhere and a cold atmosphere",
           "", "editare", "Instrucțiune"),
    Prompt("edit-desen", "Transformă în desen", "Editare · instrucțiuni",
           "Transformă fotografia în schiță în creion.",
           "turn this photo into a detailed pencil sketch drawing",
           "", "editare", "Instrucțiune"),
    Prompt("edit-acuarela", "Transformă în acuarelă", "Editare · instrucțiuni",
           "Redă imaginea ca pictură în acuarelă.",
           "turn this image into a delicate watercolor painting",
           "", "editare", "Instrucțiune"),
    Prompt("edit-sepia", "Efect vintage sepia", "Editare · instrucțiuni",
           "Fotografie veche, decolorată și granulată.",
           "make this look like an old vintage sepia photograph, faded and grainy",
           "", "editare", "Instrucțiune"),
    Prompt("edit-noapte-magica", "Noapte magică", "Editare · instrucțiuni",
           "Adaugă licurici și lumină de lună, atmosferă feerică.",
           "make it a magical night scene, glowing fireflies and moonlight",
           "", "editare", "Instrucțiune"),

    # -------------------------------------------------------- Reimaginare · stil
    Prompt("reim-scifi", "Sci-fi futurist", "Reimaginare · stil nou",
           "Reimaginează scena cu neoane și detalii cibernetice.",
           "a futuristic sci fi version of this scene, neon lights, holographic and cybernetic "
           "details, cinematic, highly detailed",
           NEG_STANDARD, "editare", "Reimaginare"),
    Prompt("reim-ulei", "Ulei impresionist", "Reimaginare · stil nou",
           "Reimaginează scena ca pictură în ulei, tușe vizibile.",
           "an impressionist oil painting of this scene, visible brush strokes, vibrant warm "
           "colors",
           NEG_STANDARD, "editare", "Reimaginare"),
    Prompt("reim-diorama", "Dioramă în miniatură", "Reimaginare · stil nou",
           "Scena ca machetă-jucărie, efect tilt-shift.",
           "a miniature toy diorama version of this scene, tilt shift effect, soft studio "
           "lighting",
           NEG_STANDARD, "editare", "Reimaginare"),
    Prompt("reim-fantezie", "Fantezie magică", "Reimaginare · stil nou",
           "Elemente magice luminoase și lumină dramatică.",
           "a fantasy version of this scene, magical glowing elements, dramatic atmospheric "
           "lighting, concept art",
           NEG_STANDARD, "editare", "Reimaginare"),
)

# Categoriile, în ordinea afișării (fără duplicate).
CATEGORIES: tuple[str, ...] = tuple(dict.fromkeys(p.categorie for p in PROMPT_LIBRARY))


def search_prompts(text: str = "", category: str = "") -> list[Prompt]:
    """Caută în librărie după text liber și/sau categorie. Returnează lista filtrată."""
    q = (text or "").strip().lower()
    out: list[Prompt] = []
    for p in PROMPT_LIBRARY:
        if category and category != "Toate categoriile" and p.categorie != category:
            continue
        if q:
            hay = f"{p.titlu} {p.descriere} {p.categorie} {p.prompt}".lower()
            if q not in hay:
                continue
        out.append(p)
    return out
