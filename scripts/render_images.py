#!/usr/bin/env python3
"""Repaint the Chinese text baked into Barrage Musical's menu textures.

Reads the four pristine Texture2D objects from the game asset files, replaces
only the Chinese lines with Korean using Pillow, and writes full-size RGBA
PNGs named after the Texture2D (assets/images/<m_Name>.png).

    python3 scripts/render_images.py --preview-dir /tmp/bxm-img
"""

import argparse
import os
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
FONT_DIR = os.path.join(REPO, "assets", "fonts")
SRC = os.path.join(REPO, "source", "BXM Tutorial Data".replace(" Data", " Tutorial_Data"))
SRC = os.path.join(REPO, "source", "BXM Tutorial_Data")
OUT = os.path.join(REPO, "assets", "images")
SS = 3

TEXTURES = {
    "MenuMain": {
        "font": "NotoSansKR-Bold.ttf",
        "style": "menu_lang",
        "items": [{"rect": (0, 205, 278, 60), "text": "한국어",
                   "ink": (43, 764, 251, 816)}],
    },
    "MenuTitle": {
        "font": "NotoSansKR-Black.ttf",
        "style": "title",
        "items": [
            {"top": 12, "text": "스테이지 선택"},
            {"top": 178, "text": "플레이어 데이터"},
            {"top": 344, "text": "음악 감상"},
            {"top": 510, "text": "리플레이"},
        ],
    },
    "GameMenu_Touhou": {
        "font": "NotoSansKR-Medium.ttf",
        "style": "menu",
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
            ("GameMenu_Touhou_SaveReplayCN", (598, 648, 300, 76), "리플레이 저장", 50, 42),
            ("GameMenu_Touhou_SaveScoreCN", (598, 548, 300, 76), "점수 기록", 50, 42),
        ],
    },
    "SpellCardName": {
        "font": "NotoSansKR-Regular.ttf",
        "style": "spell",
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
    },
}


def load_pristine(data_dir, name):
    import UnityPy

    env = UnityPy.load(os.path.join(data_dir, "resources.assets"),
                       os.path.join(data_dir, "sharedassets1.assets"))
    for obj in env.objects:
        if obj.type.name != "Texture2D":
            continue
        d = obj.read()
        if d.m_Name == name:
            return d.image.convert("RGBA")
    raise RuntimeError(name)


@dataclass
class Style:
    fill: tuple
    outline: tuple
    outline_w: int
    shadow: tuple | None = None
    shadow_off: tuple = (0, 0)
    shadow_blur: float = 0.0
    glow: tuple | None = None
    glow_w: int = 0


def style_for(name):
    if name == "menu_lang":
        return Style(((255, 255, 255), (255, 246, 238)), (188, 69, 7), 4,
                     shadow=(40, 0, 0, 70), shadow_off=(0, 2), shadow_blur=2,
                     glow=(255, 118, 24, 80), glow_w=4)
    if name == "title":
        return Style(((255, 180, 108), (255, 112, 30)), (255, 255, 255), 5,
                     shadow=(92, 26, 0, 120), shadow_off=(3, 4), shadow_blur=2)
    if name == "menu":
        return Style(((255, 255, 255), (250, 250, 250)), (0, 0, 0), 4,
                     shadow=(0, 0, 0, 170), shadow_off=(2, 2), shadow_blur=1)
    if name == "spell":
        return Style(((255, 255, 255), (215, 239, 255)), (0, 0, 0), 4,
                     shadow=(0, 0, 0, 150), shadow_off=(2, 2), shadow_blur=1)
    raise ValueError(name)


def _masks(text, font, stroke, canvas, origin):
    fill = Image.new("L", canvas, 0)
    ImageDraw.Draw(fill).text(origin, text, font=font, fill=255)
    rim = Image.new("L", canvas, 0)
    ImageDraw.Draw(rim).text(origin, text, font=font, fill=255,
                             stroke_width=stroke, stroke_fill=255)
    return fill, rim


def _fit(text, font_path, target_h, max_w):
    target = target_h * SS

    def measure(size):
        f = ImageFont.truetype(font_path, size)
        box = (10 + (len(text) + 3) * size, 10 + 4 * size)
        m = Image.new("L", box, 0)
        ImageDraw.Draw(m).text((5, 5), text, font=f, fill=255)
        return f, m.getbbox()

    lo, hi, best = 8 * SS, 260 * SS, 8 * SS
    while lo <= hi:
        mid = (lo + hi) // 2
        _, bb = measure(mid)
        if bb and bb[3] - bb[1] >= target:
            best, hi = mid, mid - 1
        else:
            lo = mid + 1
    f, bb = measure(best)
    ink_w = bb[2] - bb[0]
    scale_x = 1.0
    if ink_w > max_w * SS:
        scale_x = max(0.70, (max_w * SS) / ink_w)
        if (max_w * SS) / ink_w < 0.70:
            best = max(8 * SS, int(best * (max_w * SS) / ink_w * 0.98))
            f, bb = measure(best)
            scale_x = max_w * SS / (bb[2] - bb[0])
    return f, scale_x, bb


def draw_block(text, font_path, target_h, max_w, style):
    f, scale_x, bb = _fit(text, font_path, target_h, max_w)
    pad = int((style.outline_w + abs(style.shadow_off[0]) +
               abs(style.shadow_off[1]) + (6 if style.glow else 0) + 2) * SS)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    canvas = (tw + 2 * pad, th + 2 * pad)
    origin = (pad - bb[0], pad - bb[1])
    fill, rim = _masks(text, f, style.outline_w * SS, canvas, origin)
    layer = Image.new("RGBA", canvas, (0, 0, 0, 0))
    if style.glow:
        gm = _masks(text, f, (style.outline_w + style.glow_w) * SS, canvas,
                    origin)[1]
        gl = Image.new("RGBA", canvas, style.glow[:3] + (0,))
        gl.putalpha(gm.point(lambda v: v * style.glow[3] // 255))
        layer.alpha_composite(gl.filter(ImageFilter.GaussianBlur(2.5 * SS)))
    if style.shadow:
        sm = _masks(text, f, style.outline_w * SS, canvas,
                    (origin[0] + style.shadow_off[0] * SS,
                     origin[1] + style.shadow_off[1] * SS))[1]
        sh = Image.new("RGBA", canvas, style.shadow[:3] + (0,))
        sh.putalpha(sm.point(lambda v: v * style.shadow[3] // 255))
        if style.shadow_blur:
            sh = sh.filter(ImageFilter.GaussianBlur(style.shadow_blur * SS))
        layer.alpha_composite(sh)
    rl = Image.new("RGBA", canvas, style.outline + (255,))
    rl.putalpha(rim)
    layer.alpha_composite(rl)
    grad = Image.new("RGBA", canvas)
    px = grad.load()
    for y in range(canvas[1]):
        t = y / max(1, canvas[1] - 1)
        c = tuple(int(style.fill[0][i] * (1 - t) + style.fill[1][i] * t)
                  for i in range(3))
        for x in range(canvas[0]):
            px[x, y] = c + (255,)
    fl = grad.copy()
    fl.putalpha(fill)
    layer.alpha_composite(fl)
    bbox = layer.getbbox()
    layer = layer.crop(bbox)
    ink_x = (pad - bbox[0]) / SS
    ink_y = (pad - bbox[1]) / SS
    w = max(1, round(layer.width * scale_x / SS))
    h = max(1, round(layer.height / SS))
    layer = layer.resize((w, h), Image.LANCZOS)
    return layer, ink_x, ink_y, (tw * scale_x) / SS, th / SS


def paste(tex, layer, ix, iy, iw, ih, left, top):
    tex.alpha_composite(layer, (round(left - ix), round(top - iy)))


def render_menu_main(tex):
    cfg = TEXTURES["MenuMain"]
    st = style_for(cfg["style"])
    font = os.path.join(FONT_DIR, cfg["font"])
    for item in cfg["items"]:
        x, y, w, h = item["rect"]
        top = tex.height - y - h
        tex.paste(Image.new("RGBA", (w, h), (126, 18, 34, 0)), (x, top))
        x0, y0, x1, y1 = item["ink"]
        layer, ix, iy, iw, ih = draw_block(item["text"], font, y1 - y0 + 1,
                                           (x1 - x0) + 8, st)
        paste(tex, layer, ix, iy, iw, ih, x0, y0)


def render_menu_title(tex):
    cfg = TEXTURES["MenuTitle"]
    st = style_for(cfg["style"])
    font = os.path.join(FONT_DIR, cfg["font"])
    for item in cfg["items"]:
        top = item["top"]
        band = (219, top + 14, 701, top + 95)
        tex.paste(Image.new("RGBA", (band[2] - band[0], band[3] - band[1]),
                            (255, 136, 44, 0)), band[:2])
        staff(tex, top, 219, 701)
        layer, ix, iy, iw, ih = draw_block(item["text"], font, 71, 465, st)
        paste(tex, layer, ix, iy, iw, ih, 231, top + 19)


def staff(tex, top, x0, x1):
    arr = np.array(tex)
    for rel in (36, 37, 38, 60, 61, 62, 85, 86, 87):
        y = top + rel
        a0 = int(arr[y, 216, 3])
        for x in range(x0, x1):
            if x <= 216:
                continue
            ramp = min(1.0, (x - 216) / 384.0)
            a = a0 + (255 - a0) * ramp
            if x > 620:
                a *= max(0.0, (699 - x) / 79.0)
            arr[y, x] = (255, 182, 102, max(int(arr[y, x, 3]), int(round(a))))
    tex.paste(Image.fromarray(arr))


CENTERED = {"GameMenu_Touhou_Pause", "GameMenu_Touhou_Clear",
            "GameMenu_Touhou_GameOver", "GameMenu_Touhou_SaveReplayCN",
            "GameMenu_Touhou_SaveScoreCN"}


def render_game_menu(tex):
    cfg = TEXTURES["GameMenu_Touhou"]
    st = style_for(cfg["style"])
    font = os.path.join(FONT_DIR, cfg["font"])
    for name, rect, text, left, _th in cfg["items"]:
        x, y, w, h = rect
        top = tex.height - y - h
        tex.paste(Image.new("RGBA", (w, 48), (0, 0, 0, 0)), (x, top))
        # 35px ink height keeps the Korean clear of the English subtitle at y+48
        layer, ix, iy, iw, ih = draw_block(text, font, 35, w - left - 3, st)
        if name in CENTERED:
            left = (w - iw) / 2
        paste(tex, layer, ix, iy, iw, ih, x + left, top + 4)


def render_spell_cards(tex):
    cfg = TEXTURES["SpellCardName"]
    st = style_for(cfg["style"])
    font = os.path.join(FONT_DIR, cfg["font"])
    for _n, rect, text, left, iy, th in cfg["items"]:
        x, y, w, h = rect
        top = tex.height - y - h
        tex.paste(Image.new("RGBA", (w, h), (0, 0, 0, 0)), (x, top))
        layer, ix, iy2, iw, ih = draw_block(text, font, th, w - left - 4, st)
        paste(tex, layer, ix, iy2, iw, ih, x + left,
              top + iy + (th - ih) / 2)


RENDERERS = {"MenuMain": render_menu_main, "MenuTitle": render_menu_title,
             "GameMenu_Touhou": render_game_menu, "SpellCardName": render_spell_cards}


def changed_rects(name, tex):
    cfg = TEXTURES[name]
    rects = []
    if name == "MenuMain":
        for it in cfg["items"]:
            x, y, w, h = it["rect"]
            rects.append((x, tex.height - y - h, w, h))
    elif name == "MenuTitle":
        for it in cfg["items"]:
            rects.append((219, it["top"] + 14, 701 - 219, 81))
    elif name == "GameMenu_Touhou":
        for _n, rect, _t, _l, _th in cfg["items"]:
            x, y, w, h = rect
            rects.append((x, tex.height - y - h, w, 48))
    else:
        for _n, rect, _t, _l, _iy, _th in cfg["items"]:
            x, y, w, h = rect
            rects.append((x, tex.height - y - h, w, h))
    return rects


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--preview-dir", default=None)
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    names = [n.strip() for n in a.only.split(",")] if a.only else list(RENDERERS)
    for name in names:
        orig = load_pristine(a.src, name)
        new = orig.copy()
        RENDERERS[name](new)
        # keep everything outside the declared text rects byte-identical
        final = orig.copy()
        for (x, y, w, h) in changed_rects(name, orig):
            final.paste(new.crop((x, y, x + w, y + h)), (x, y))
        new = final
        new.save(os.path.join(a.out, name + ".png"))
        assert new.size == orig.size
        print(f"{name}: {new.width}x{new.height}")
        if a.preview_dir:
            os.makedirs(a.preview_dir, exist_ok=True)
            pad = 12
            prev = Image.new("RGBA", (orig.width * 2 + pad * 3, orig.height + 2 * pad),
                             (24, 24, 32, 255))
            prev.alpha_composite(orig, (pad, pad))
            prev.alpha_composite(new, (pad * 2 + orig.width, pad))
            prev.convert("RGB").save(os.path.join(a.preview_dir, f"preview_{name}.png"))


if __name__ == "__main__":
    main()
