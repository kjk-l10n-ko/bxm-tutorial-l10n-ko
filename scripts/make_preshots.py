#!/usr/bin/env python3
"""Black-text preshots + final compositing for the four repainted textures.

The Korean lettering itself is drawn by the Seedream pipeline in kjk-comfyUI:
for every texture we send (1) the original region on a flat green background
and (2) a plain-black BM Jua preshot that fixes spelling, position and size.
This script writes those two references and the tree _config.json, then (after
the generation runs) keys the green background out and pastes only the text
rectangles back into the pristine texture.

    python3 scripts/make_preshots.py preshots
    python3 scripts/make_preshots.py composite

Both read/write the comfyUI trees under $COMFY_ROOT/output/bxm/<texture>/.
"""

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC = os.path.join(REPO, "source", "BXM Tutorial_Data")
OUT = os.path.join(REPO, "assets", "images")
COMFY_ROOT = os.environ.get("COMFY_ROOT", "/mnt/h/02_Workspace/40_WSL/kjk-comfyUI")
JUA = os.environ.get(
    "PRESHOT_FONT",
    "/mnt/h/02_Workspace/40_WSL/font-libs/fonts/우아한형제들/주아체/BMJUA_ttf.ttf",
)
FALLBACK = os.path.join(REPO, "assets", "fonts", "NotoSansKR-Regular.ttf")
KEY = (255, 0, 255)

# --- per-texture description ---------------------------------------------

TREES = {
    "MenuMain": {
        "crop": (0, 752, 300, 76),          # region sent to the model
        "scale": 6.53,                       # approx; output size below wins
        "size": (1960, 496),
        "pastes": [(0, 752, 300, 76)],
        "items": [
            {"text": "한국어", "left": 43, "top": 764, "h": 53},
        ],
        "prompt": (
            "Game UI text redrawn from image 1, with the Chinese language label "
            "replaced by Korean. Copy image 1 exactly: same white fill, orange-red "
            "outline, soft orange glow, same glyph size, weight and position. "
            "Image 2 is only a spelling and placement guide in plain black text: "
            "use its exact Korean word \"한국어\", its position and size, but do not "
            "copy its black plain look or typeface. Flat solid pure magenta (#FF00FF) "
            "background edge to edge, no magenta or pink on the artwork."
        ),
    },
    "MenuTitle": {
        "crop": (0, 0, 752, 750),
        "size": (1504, 1500),
        "pastes": None,  # per item: clear band and paste the same band
        "paste_band": (225, 14, 701, 95),  # relative to item top
        "items": [
            {"text": "스테이지 선택", "top": 12, "left": 231, "ink_top": 19, "h": 71},
            {"text": "플레이어 데이터", "top": 178, "left": 231, "ink_top": 19, "h": 71},
            {"text": "음악 감상", "top": 344, "left": 231, "ink_top": 19, "h": 71},
            {"text": "리플레이", "top": 510, "left": 231, "ink_top": 19, "h": 71},
        ],
        "prompt": (
            "Game menu title art redrawn from image 1, with the four Chinese "
            "headings replaced by Korean. Copy image 1 exactly: same orange staff "
            "lines, treble clefs, glow, white outer outline and orange gradient "
            "fill; keep the English subtitles \"Stage Select\", \"Player Data\", "
            "\"Music Room\", \"Replay\" unchanged below each heading. Image 2 is "
            "only a spelling and placement guide in plain black text: use its exact "
            "Korean words \"스테이지 선택\", \"플레이어 데이터\", \"음악 감상\", "
            "\"리플레이\" at its positions and sizes, but do not copy its black "
            "plain look or typeface. Flat solid pure magenta (#FF00FF) background edge "
            "to edge, no magenta or pink on the artwork."
        ),
    },
    "GameMenu_Touhou": {
        "crop": (0, 0, 1024, 1024),
        "size": (1536, 1536),
        "pastes": None,  # per item: (x, top, w, 48)
        "items": [
            ("GameMenu_Touhou_Resume", (0, 942, 255, 76), "계속하기", 5, 42),
            ("GameMenu_Touhou_TeStart", (0, 846, 274, 75), "처음부터", 5, 42),
            ("GameMenu_Touhou_Return", (1, 748, 436, 77), "타이틀로", 4, 42),
            ("GameMenu_Touhou_TryAgain", (0, 652, 309, 77), "다시 도전", 4, 42),
            ("GameMenu_Touhou_Next", (0, 555, 350, 76), "다음 스테이지", 5, 42),
            ("GameMenu_Touhou_SaveRep", (0, 461, 364, 72), "리플레이 저장", 4, 42),
            ("GameMenu_Touhou_Yes", (0, 367, 116, 71), "예", 4, 42),
            ("GameMenu_Touhou_No", (0, 271, 91, 73), "아니요", 4, 42),
            ("GameMenu_Touhou_TutorialRep", (0, 171, 437, 76), "튜토리얼 리플레이", 3, 42),
            ("GameMenu_Touhou_Pause", (598, 931, 295, 87), "일시 정지", 51, 42),
            ("GameMenu_Touhou_Clear", (598, 832, 295, 89), "올 클리어", 50, 42),
            ("GameMenu_Touhou_GameOver", (598, 736, 296, 87), "게임 오버", 49, 42),
            ("GameMenu_Touhou_Leaderboard", (0, 60, 465, 89), "순위표 보기", 5, 42),
        ],
        "prompt": (
            "Game menu labels redrawn from image 1, with the thirteen Chinese "
            "labels replaced by Korean. Copy image 1 exactly: same white fill, "
            "black outline and drop shadow, same positions and sizes; keep all "
            "peach English subtitles unchanged below the labels. Image 2 is only a "
            "spelling and placement guide in plain black text: use its exact Korean "
            "words \"계속하기\", \"처음부터\", \"타이틀로\", \"다시 도전\", "
            "\"다음 스테이지\", \"리플레이 저장\", \"예\", \"아니요\", "
            "\"튜토리얼 리플레이\", \"순위표 보기\", \"일시 정지\", \"올 클리어\", "
            "\"게임 오버\" at its positions and sizes, but do not copy its black "
            "plain look or typeface. Flat solid pure magenta (#FF00FF) background edge "
            "to edge, no magenta or pink on the artwork."
        ),
    },
    "SpellCardName": {
        "crop": (0, 0, 900, 645),
        "size": (1170, 839),
        "pastes": None,  # per item: sprite rect
        "items": [
            ("SC01", (0, 962, 422, 58), "거울부「전역 반사」", 9, 2, 51),
            ("SC02", (0, 900, 479, 57), "사미센「고양이의 연주」", 12, 4, 50),
            ("SC03", (0, 834, 645, 61), "도약부「치냥·퐁냥·깡냥」", 7, 6, 50),
            ("SC04", (1, 771, 481, 58), "고양이부「리듬 캣워크」", 7, 4, 50),
            ("SC05", (0, 707, 534, 59), "선언「나는 여우가 아니야」", 9, 5, 50),
            ("SC06", (0, 642, 412, 59), "사격「FPS 게이머」", 9, 3, 51),
            ("SC07", (0, 576, 480, 62), "회상「나이의 원념」", 11, 4, 51),
            ("SC08", (0, 514, 316, 58), "율부「담뱃잎」", 9, 3, 50),
            ("SC09", (31, 449, 507, 60), "「고양이들의 왕국으로」", 8, 4, 50),
            ("SC10", (0, 385, 664, 60), "저주「마법소녀 고양이가 되어라!」", 10, 3, 51),
        ],
        "prompt": (
            "Ten spell-card names redrawn from image 1, with the Chinese names "
            "replaced by Korean. Copy image 1 exactly: same white fill with a pale "
            "ice-blue sheen, black outline and drop shadow, same positions and "
            "sizes. Image 2 is only a spelling and placement guide in plain black "
            "text: use its exact Korean words \"거울부「전역 반사」\", "
            "\"사미센「고양이의 연주」\", \"도약부「치냥·퐁냥·깡냥」\", "
            "\"고양이부「리듬 캣워크」\", \"선언「나는 여우가 아니야」\", "
            "\"사격「FPS 게이머」\", \"회상「나이의 원념」\", \"율부「담뱃잎」\", "
            "\"「고양이들의 왕국으로」\", \"저주「마법소녀 고양이가 되어라!」\" at "
            "its positions and sizes, but do not copy its black plain look or "
            "typeface. Flat solid pure magenta (#FF00FF) background edge to edge, "
            "no magenta or pink on the artwork."
        ),
    },
}


# --- pristine texture -----------------------------------------------------

def load_pristine(name):
    import UnityPy

    env = UnityPy.load(
        os.path.join(SRC, "resources.assets"),
        os.path.join(SRC, "sharedassets1.assets"),
    )
    for obj in env.objects:
        if obj.type.name != "Texture2D":
            continue
        data = obj.read()
        if data.m_Name == name:
            return data.image.convert("RGBA")
    raise RuntimeError(name)


def tree_dir(name):
    return os.path.join(COMFY_ROOT, "output", "bxm", name, "00_resource", "01_key_frame")


# --- preshot --------------------------------------------------------------

def ink_font(text, height):
    """BM Jua sized so the ink height is exactly `height` pixels."""
    lo, hi, best = 8, 1500, 8
    while lo <= hi:
        mid = (lo + hi) // 2
        f = ImageFont.truetype(JUA, mid)
        mask = Image.new("L", (8 * mid * max(1, len(text)), 4 * mid), 0)
        ImageDraw.Draw(mask).text((5, 5), text, font=f, fill=255)
        bb = mask.getbbox()
        if bb and bb[3] - bb[1] >= height:
            best, hi = mid, mid - 1
        else:
            lo = mid + 1
    return ImageFont.truetype(JUA, best)


def draw_guide(draw, text, left, top, height):
    """Plain black guide text; BM Jua for Hangul, Noto for glyphs Jua lacks."""
    f = ink_font(text, height)
    fb = ImageFont.truetype(FALLBACK, round(f.size * 0.94))
    baseline = top + f.getmetrics()[0]
    x = left
    for ch in text:
        miss = f.getmask(ch).getbbox() is None and not ch.isspace()
        use = fb if miss else f
        draw.text((x, baseline), ch, font=use, fill=(0, 0, 0), anchor="ls")
        x += use.getlength(ch)


def scaled_item(name, item, sx, sy):
    """Return (text, left*, top*, height*) in generated-canvas pixels."""
    if name == "MenuTitle":
        return (item["text"], item["left"], item["top"] + item["ink_top"], item["h"])
    if name == "GameMenu_Touhou":
        _, rect, text, left, h = item
        top = 1024 - rect[1] - rect[3] + 4
        return (text, rect[0] + left, top, h)
    if name == "SpellCardName":
        _, rect, text, left, iy, h = item
        top = 1024 - rect[1] - rect[3] + iy
        return (text, rect[0] + left, top, h)
    return (item["text"], item["left"] - TREES[name]["crop"][0],
            item["top"] - TREES[name]["crop"][1], item["h"])


def make_preshots(only=None):
    for name, cfg in TREES.items():
        if only and name not in only:
            continue
        tex = load_pristine(name)
        crop = cfg["crop"]
        region = tex.crop((crop[0], crop[1], crop[0] + crop[2], crop[1] + crop[3]))
        size = cfg["size"]
        sx, sy = size[0] / region.width, size[1] / region.height

        # reference: original region on the flat key colour
        # the model gets the art at generation scale on the flat key colour
        up = region.resize(size, Image.LANCZOS)
        bg = Image.new("RGBA", size, KEY + (255,))
        ref = Image.alpha_composite(bg, up).convert("RGB")

        # preshot: plain black Korean on white, exact positions/sizes
        pre = Image.new("RGB", size, (255, 255, 255))
        d = ImageDraw.Draw(pre)
        for item in cfg["items"]:
            text, left, top, h = scaled_item(name, item, sx, sy)
            draw_guide(d, text, round(left * sx), round(top * sy), round(h * sy))

        td = tree_dir(name)
        os.makedirs(os.path.join(td, "ref"), exist_ok=True)
        ref.save(os.path.join(td, "ref", "original.png"))
        pre.save(os.path.join(td, "ref", "preshot_black.png"))
        config = {
            "prompt": cfg["prompt"],
            "reference_image_note": (
                "ref/original.png = original texture region on flat green; "
                "ref/preshot_black.png = black text spelling/placement guide"
            ),
            "max_dimension": max(size),
            "api_parameter": {
                "platform": "byteplus",
                "model": "dola-seedream-5-0-flash-260915",
                "reference_image": f"output/bxm/{name}/00_resource/01_key_frame/ref/original.png",
                "additional_reference_images": [
                    f"output/bxm/{name}/00_resource/01_key_frame/ref/preshot_black.png"
                ],
                "size": f"{size[0]}x{size[1]}",
                "output_format": "png",
                "response_format": None,
                "watermark": False,
                "background": None,
                "optimize_prompt_options": None,
                "layer_decomposition": None,
            },
            "note": "",
            "additional_reference_images": [
                f"output/bxm/{name}/00_resource/01_key_frame/ref/preshot_black.png"
            ],
        }
        with open(os.path.join(td, "_config.json"), "w", encoding="utf-8") as fh:
            json.dump(config, fh, ensure_ascii=False, indent=1)
        print(f"{name}: ref {size} preshot {size} -> {td}")


# --- compositing ----------------------------------------------------------

def key_magenta(img):
    """Unmix the flat magenta background instead of a hard matte.

    dom = min(R,B) - G is 255 on pure magenta, 0 on white and negative on warm
    art.  alpha = 1 - dom makes AA edges orthogonal to the key colour, then the
    foreground is recovered from C = a*F + (1-a)*(255,0,255).
    """
    arr = np.array(img.convert("RGB")).astype(np.float32)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    dom = np.minimum(r, b) - g
    a = np.clip(255.0 - dom, 0.0, 255.0)
    a[dom < -30] = 255.0
    an = a / 255.0
    fg = (arr - (1.0 - an[:, :, None]) * np.array([255, 0, 255])) / np.maximum(
        an[:, :, None], 1e-6)
    fg = np.clip(fg, 0, 255)
    a[a < 31] = 0
    out = np.dstack([fg[:, :, 0], fg[:, :, 1], fg[:, :, 2], a]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def drop_peach(img):
    """GameMenu: the model redraws the peach English subtitles badly; keep the
    original ones by dropping every warm-toned pixel from the generated art."""
    arr = np.array(img)
    r, g, b, a = (arr[:, :, i].astype(np.int16) for i in range(4))
    peach = (r > 165) & (r - b > 30) & (g > 110)
    arr[:, :, 3] = np.where(peach, 0, a)
    return Image.fromarray(arr, "RGBA")


def composite(only=None):
    os.makedirs(OUT, exist_ok=True)
    for name, cfg in TREES.items():
        if only and name not in only:
            continue
        tex = load_pristine(name)
        base_path = os.path.join(tree_dir(name), "base.png")
        gen = Image.open(base_path).convert("RGB")
        crop = cfg["crop"]
        gen = key_magenta(gen)
        if name == "GameMenu_Touhou":
            gen = drop_peach(gen)
        gen = gen.resize((crop[2], crop[3]), Image.LANCZOS)
        origin = (crop[0], crop[1])

        if cfg.get("pastes"):
            for (x, y, w, h) in cfg["pastes"]:
                box = (x - origin[0], y - origin[1], x - origin[0] + w, y - origin[1] + h)
                tex.paste(Image.new("RGBA", (w, h), (0, 0, 0, 0)), (x, y))
                tex.alpha_composite(gen.crop(box), (x, y))
        else:
            for item in cfg["items"]:
                if name == "MenuTitle":
                    x0 = cfg["paste_band"][0]
                    y0 = item["top"] + cfg["paste_band"][1]
                    x1 = cfg["paste_band"][2]
                    y1 = item["top"] + cfg["paste_band"][3]
                elif name == "GameMenu_Touhou":
                    _, rect, _t, _l, _h = item
                    x0, y0 = rect[0], 1024 - rect[1] - rect[3]
                    x1, y1 = x0 + rect[2], y0 + rect[3]
                else:  # SpellCardName
                    _, rect, _t, _l, _iy, _h = item
                    x0, y0 = rect[0], 1024 - rect[1] - rect[3]
                    x1, y1 = x0 + rect[2], y0 + rect[3]
                w, h = x1 - x0, y1 - y0
                box = (x0 - origin[0], y0 - origin[1],
                       x0 - origin[0] + w, y0 - origin[1] + h)
                clear_h = 48 if name == "GameMenu_Touhou" else h
                tex.paste(Image.new("RGBA", (w, clear_h), (0, 0, 0, 0)), (x0, y0))
                tex.alpha_composite(gen.crop(box), (x0, y0))

        path = os.path.join(OUT, name + ".png")
        tex.save(path)
        print(f"{name}: {tex.width}x{tex.height} -> {path}")
        assert tex.size == load_pristine(name).size

        origin_img = load_pristine(name)
        pad = 12
        w = origin_img.width
        prev = Image.new("RGBA", (w * 2 + pad * 3, origin_img.height + 2 * pad),
                         (24, 24, 32, 255))
        prev.alpha_composite(origin_img, (pad, pad))
        prev.alpha_composite(tex, (pad * 2 + w, pad))
        prev.convert("RGB").save(f"/tmp/bxm-img/preview_{name}.png")
        for label, col in (("black", (0, 0, 0, 255)), ("white", (255, 255, 255, 255))):
            flat = Image.new("RGBA", tex.size, col)
            flat.alpha_composite(tex)
            flat.convert("RGB").save(f"/tmp/bxm-img/preview_{name}_{label}.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["preshots", "composite"])
    ap.add_argument("--only", default=None)
    args = ap.parse_args()
    only = [n.strip() for n in args.only.split(",")] if args.only else None
    (make_preshots if args.action == "preshots" else composite)(only)


if __name__ == "__main__":
    main()
