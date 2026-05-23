import base64
import io
import json
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from bead_generator import image_to_bead_pattern
from palettes import get_palette_list, get_palette
from pdf_export import generate_bead_pdf

# Eager-load rembg to avoid first-request timeout
try:
    from rembg import remove
except ImportError:
    remove = None

BASE_DIR = Path(__file__).resolve().parent
CARDS_FILE = BASE_DIR / "cards.json"

MAX_FREE_GRID = 50
MAX_CARD_GRID = 300

app = FastAPI(title="拼豆图纸生成器")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Models ---

class ColorInfo(BaseModel):
    hex: str
    name: str
    code: str
    index: int
    count: int


class PatternResponse(BaseModel):
    image_base64: str
    palette_id: str
    colors_used: List[ColorInfo]
    grid_width: int
    grid_height: int
    total_beads: int
    locked: bool  # True = need card to download/modify


class PaletteInfo(BaseModel):
    id: str
    name: str
    color_count: int


class PaletteDetail(BaseModel):
    id: str
    name: str
    colors: dict


class UnlockRequest(BaseModel):
    card_code: str


class UnlockResponse(BaseModel):
    valid: bool
    message: str
    expires_at: Optional[str] = None
    duration_days: int = 0


class PDFExportRequest(BaseModel):
    image_base64: str
    grid_width: int
    grid_height: int
    colors_used: List[ColorInfo]
    palette_name: str
    card_code: str


# --- Card helpers ---

def load_cards():
    if not CARDS_FILE.exists():
        return []
    try:
        with CARDS_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def find_card(code: str):
    cards = load_cards()
    return next((card for card in cards if card["code"] == code), None)


def validate_card(code: str):
    """Returns card dict or raises HTTPException. Activation tracking is client-side."""
    card = find_card(code)
    if not card:
        raise HTTPException(status_code=400, detail="卡密无效")
    return card


# --- Endpoints ---

@app.get("/palettes", response_model=List[PaletteInfo])
def list_palettes():
    return get_palette_list()


@app.get("/palettes/{palette_id}", response_model=PaletteDetail)
def get_palette_detail(palette_id: str):
    palette = get_palette(palette_id)
    if not palette:
        raise HTTPException(status_code=404, detail="色板不存在")
    return {"id": palette_id, "name": palette["name"], "colors": palette["colors"]}


def _parse_bool(val: str) -> bool:
    return val.lower() in ("true", "1", "on", "yes")


def _build_kwargs(grid_width, grid_height, palette_id, max_colors,
                   brightness, contrast, saturation, dithering,
                   flip_h, flip_v, show_grid, transparent_bg, pixelate,
                   exclude_colors_str="", merge_value=0, show_coords=True,
                   highlight_index=-1, replace_colors_str=""):
    exclude_colors = []
    if exclude_colors_str:
        try:
            exclude_colors = json.loads(exclude_colors_str)
        except (json.JSONDecodeError, TypeError):
            pass
    replace_colors = {}
    if replace_colors_str:
        try:
            replace_colors = json.loads(replace_colors_str)
        except (json.JSONDecodeError, TypeError):
            pass
    return dict(
        grid_width=grid_width,
        grid_height=grid_height,
        palette_id=palette_id,
        max_colors=max_colors,
        brightness=brightness,
        contrast=contrast,
        saturation=saturation,
        dithering=_parse_bool(dithering) if isinstance(dithering, str) else dithering,
        flip_h=_parse_bool(flip_h) if isinstance(flip_h, str) else flip_h,
        flip_v=_parse_bool(flip_v) if isinstance(flip_v, str) else flip_v,
        show_grid=_parse_bool(show_grid) if isinstance(show_grid, str) else show_grid,
        transparent_bg=_parse_bool(transparent_bg) if isinstance(transparent_bg, str) else transparent_bg,
        pixelate=_parse_bool(pixelate) if isinstance(pixelate, str) else pixelate,
        exclude_colors=exclude_colors,
        merge_value=int(merge_value),
        show_coords=_parse_bool(show_coords) if isinstance(show_coords, str) else show_coords,
        highlight_index=int(highlight_index),
        replace_colors=replace_colors,
    )


@app.post("/generate", response_model=PatternResponse)
async def generate_pattern(
    image: UploadFile = File(...),
    grid_width: int = Form(48),
    grid_height: int = Form(0),
    palette_id: str = Form("default"),
    max_colors: int = Form(0),
    brightness: float = Form(1.0),
    contrast: float = Form(1.0),
    saturation: float = Form(1.0),
    dithering: str = Form("true"),
    flip_h: str = Form("false"),
    flip_v: str = Form("false"),
    show_grid: str = Form("true"),
    transparent_bg: str = Form("false"),
    pixelate: str = Form("false"),
    exclude_colors: str = Form(""),
    merge_value: int = Form(0),
    show_coords: str = Form("true"),
    highlight_index: int = Form(-1),
    replace_colors: str = Form(""),
):
    if image.content_type.split("/")[0] != "image":
        raise HTTPException(status_code=400, detail="请上传图片文件")

    if palette_id not in {p["id"] for p in get_palette_list()}:
        raise HTTPException(status_code=400, detail="未知色板")

    if grid_width < 1 or grid_width > MAX_FREE_GRID:
        raise HTTPException(status_code=400, detail=f"宽度范围 1-{MAX_FREE_GRID}")
    if grid_height < 0 or (grid_height > 0 and grid_height > MAX_FREE_GRID):
        raise HTTPException(status_code=400, detail=f"高度范围 1-{MAX_FREE_GRID}")

    if max_colors < 0 or max_colors > 50:
        raise HTTPException(status_code=400, detail="颜色数范围 0-50")

    image_bytes = await image.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片文件不能超过10MB")

    try:
        kwargs = _build_kwargs(grid_width, grid_height, palette_id, max_colors,
                               brightness, contrast, saturation, dithering,
                               flip_h, flip_v, show_grid, transparent_bg, pixelate,
                               exclude_colors, merge_value, show_coords,
                               highlight_index, replace_colors)
        result = image_to_bead_pattern(image_bytes, **kwargs)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"图片处理失败: {str(e)}")

    return {
        "image_base64": result["image_base64"],
        "palette_id": result["palette_id"],
        "colors_used": result["colors_used"],
        "grid_width": result["grid_width"],
        "grid_height": result["grid_height"],
        "total_beads": result["total_beads"],
        "locked": True,
    }


@app.post("/unlock", response_model=UnlockResponse)
async def unlock_card(req: UnlockRequest):
    """Validate card code. Activation tracking is client-side."""
    try:
        card = validate_card(req.card_code)
        return {
            "valid": True,
            "message": "卡密验证成功",
            "expires_at": None,
            "duration_days": card["duration_days"],
        }
    except HTTPException as e:
        return {"valid": False, "message": e.detail}


@app.post("/regenerate")
async def regenerate_pattern(
    image: UploadFile = File(...),
    grid_width: int = Form(48),
    grid_height: int = Form(0),
    palette_id: str = Form("default"),
    max_colors: int = Form(0),
    brightness: float = Form(1.0),
    contrast: float = Form(1.0),
    saturation: float = Form(1.0),
    dithering: str = Form("true"),
    flip_h: str = Form("false"),
    flip_v: str = Form("false"),
    show_grid: str = Form("true"),
    transparent_bg: str = Form("false"),
    pixelate: str = Form("false"),
    exclude_colors: str = Form(""),
    merge_value: int = Form(0),
    show_coords: str = Form("true"),
    highlight_index: int = Form(-1),
    replace_colors: str = Form(""),
    card_code: str = Form(...),
):
    validate_card(card_code)

    if palette_id not in {p["id"] for p in get_palette_list()}:
        raise HTTPException(status_code=400, detail="未知色板")

    if grid_width < 1 or grid_width > MAX_CARD_GRID:
        raise HTTPException(status_code=400, detail=f"宽度范围 1-{MAX_CARD_GRID}")
    if grid_height < 0 or (grid_height > 0 and grid_height > MAX_CARD_GRID):
        raise HTTPException(status_code=400, detail=f"高度范围 1-{MAX_CARD_GRID}")

    if max_colors < 0 or max_colors > 50:
        raise HTTPException(status_code=400, detail="颜色数范围 0-50")

    image_bytes = await image.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片文件不能超过10MB")

    try:
        kwargs = _build_kwargs(grid_width, grid_height, palette_id, max_colors,
                               brightness, contrast, saturation, dithering,
                               flip_h, flip_v, show_grid, transparent_bg, pixelate,
                               exclude_colors, merge_value, show_coords,
                               highlight_index, replace_colors)
        result = image_to_bead_pattern(image_bytes, **kwargs)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"图片处理失败: {str(e)}")

    return {
        "image_base64": result["image_base64"],
        "palette_id": result["palette_id"],
        "colors_used": result["colors_used"],
        "grid_width": result["grid_width"],
        "grid_height": result["grid_height"],
        "total_beads": result["total_beads"],
        "locked": False,
    }


@app.post("/export-pdf")
async def export_pdf(req: PDFExportRequest):
    try:
        validate_card(req.card_code)
    except HTTPException as e:
        raise HTTPException(status_code=403, detail="需要有效卡密才能导出PDF")

    try:
        pdf_bytes = generate_bead_pdf(
            image_base64=req.image_base64,
            grid_width=req.grid_width,
            grid_height=req.grid_height,
            colors_used=[c.model_dump() for c in req.colors_used],
            palette_name=req.palette_name,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF生成失败: {str(e)}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=bead-pattern.pdf"},
    )


@app.post("/remove-bg")
async def remove_background(image: UploadFile = File(...)):
    if remove is None:
        raise HTTPException(status_code=501, detail="抠图服务未安装（缺少 rembg）")

    if image.content_type.split("/")[0] != "image":
        raise HTTPException(status_code=400, detail="请上传图片文件")

    image_bytes = await image.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片文件不能超过10MB")

    try:
        from PIL import Image

        result_bytes = remove(image_bytes)

        # Convert RGBA to white background PNG
        img = Image.open(io.BytesIO(result_bytes)).convert("RGBA")
        white_bg = Image.new("RGB", img.size, (255, 255, 255))
        white_bg.paste(img, mask=img.split()[3])

        buf = io.BytesIO()
        white_bg.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")

        return {"image_base64": b64}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"抠图失败: {str(e)}")
