import base64
import io
from collections import Counter
from typing import List

from PIL import Image, ImageDraw, ImageFont, ImageEnhance

from palettes import get_color_hex_list, get_color_entries


def _hex_to_rgb(color_hex: str) -> tuple:
    color = color_hex.lstrip("#")
    return tuple(int(color[i:i+2], 16) for i in (0, 2, 4))


def _get_font(size: int):
    font_paths = [
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        # Linux - Noto CJK
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
        # Linux - WenQuanYi
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/wqy-microhei/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc",
        # Linux - Droid / Liberation
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        # Linux - DejaVu (no CJK but better than nothing)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for fp in font_paths:
        try:
            return ImageFont.truetype(fp, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def build_palette_image(hex_list: List[str]) -> Image.Image:
    palette_image = Image.new("P", (1, 1))
    palette_data = []
    for hex_color in hex_list:
        palette_data.extend(_hex_to_rgb(hex_color))
    palette_data += [0] * (768 - len(palette_data))
    palette_image.putpalette(palette_data)
    return palette_image


def _is_dark(hex_color: str) -> bool:
    r, g, b = _hex_to_rgb(hex_color)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return luminance < 128


def _color_distance(hex1: str, hex2: str) -> float:
    r1, g1, b1 = _hex_to_rgb(hex1)
    r2, g2, b2 = _hex_to_rgb(hex2)
    return ((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2) ** 0.5


def _merge_similar_colors(grid_data, counter, hex_list, color_entries, merge_value):
    """Merge similar colors based on merge_value. Returns (new_grid_data, new_counter, new_entries, index_map, used_indices)."""
    if merge_value <= 0 or len(counter) <= 2:
        return grid_data, counter, color_entries, None, None

    used_indices = sorted(counter.keys())
    if len(used_indices) <= 2:
        return grid_data, counter, color_entries, None, None

    threshold = merge_value * 3.0
    merged_grid = list(grid_data)

    while len(used_indices) > 2:
        min_dist = float('inf')
        merge_pair = None
        for i in range(len(used_indices)):
            for j in range(i + 1, len(used_indices)):
                d = _color_distance(hex_list[used_indices[i]], hex_list[used_indices[j]])
                if d < min_dist:
                    min_dist = d
                    merge_pair = (i, j)
        if min_dist > threshold:
            break
        i_idx, j_idx = merge_pair
        idx_a, idx_b = used_indices[i_idx], used_indices[j_idx]
        if counter.get(idx_b, 0) > counter.get(idx_a, 0):
            idx_a, idx_b = idx_b, idx_a
        for k in range(len(merged_grid)):
            if merged_grid[k] == idx_b:
                merged_grid[k] = idx_a
        counter[idx_a] = counter.get(idx_a, 0) + counter.pop(idx_b, 0)
        used_indices.remove(idx_b)

    new_counter = Counter()
    for val in merged_grid:
        new_counter[val] += 1
    new_entries = [color_entries[i] for i in used_indices]
    index_map = {old: new for new, old in enumerate(used_indices)}
    remapped_grid = [index_map[v] for v in merged_grid]
    return remapped_grid, new_counter, new_entries, index_map, used_indices


def image_to_bead_pattern(
    image_bytes: bytes,
    grid_width: int = 48,
    grid_height: int = 0,
    palette_id: str = "default",
    max_colors: int = 0,
    brightness: float = 1.0,
    contrast: float = 1.0,
    saturation: float = 1.0,
    dithering: bool = True,
    flip_h: bool = False,
    flip_v: bool = False,
    show_grid: bool = True,
    transparent_bg: bool = False,
    pixelate: bool = False,
    exclude_colors: List[int] = None,
    merge_value: int = 0,
    show_coords: bool = True,
    highlight_index: int = -1,
    replace_colors: dict = None,
) -> dict:
    full_hex_list = get_color_hex_list(palette_id)
    full_color_entries = get_color_entries(palette_id)

    if 0 < max_colors < len(full_hex_list):
        hex_list = full_hex_list[:max_colors]
        color_entries = full_color_entries[:max_colors]
    else:
        hex_list = full_hex_list
        color_entries = full_color_entries

    # Remove excluded colors from palette
    # Build orig_idx -> filtered_idx map (for highlight lookup)
    orig_to_filtered = {i: i for i in range(len(full_hex_list))}
    if exclude_colors:
        exclude_set = set(exclude_colors)
        hex_list = [c for i, c in enumerate(hex_list) if i not in exclude_set]
        color_entries = [c for i, c in enumerate(color_entries) if i not in exclude_set]
        orig_to_filtered = {}
        filtered_idx = 0
        for i in range(len(full_hex_list)):
            if i not in exclude_set:
                orig_to_filtered[i] = filtered_idx
                filtered_idx += 1

    with Image.open(io.BytesIO(image_bytes)) as image:
        image = image.convert("RGBA")

        # Calculate target size
        if grid_height <= 0:
            aspect = image.height / image.width
            grid_height = max(1, int(grid_width * aspect))

        # Apply flips
        if flip_h:
            image = image.transpose(Image.FLIP_LEFT_RIGHT)
        if flip_v:
            image = image.transpose(Image.FLIP_TOP_BOTTOM)

        # Resize
        new_size = (grid_width, grid_height)
        if pixelate:
            # Pixelate: resize to small then back up with NEAREST
            tiny = image.resize(new_size, Image.NEAREST)
            image = tiny
        else:
            image = image.resize(new_size, Image.LANCZOS)

        # Apply brightness, contrast, saturation
        if brightness != 1.0:
            enhancer = ImageEnhance.Brightness(image)
            image = enhancer.enhance(brightness)
        if contrast != 1.0:
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(contrast)
        if saturation != 1.0:
            enhancer = ImageEnhance.Color(image)
            image = enhancer.enhance(saturation)

        # Quantize
        palette_img = build_palette_image(hex_list)
        dither_mode = Image.FLOYDSTEINBERG if dithering else Image.NONE
        quantized = image.convert("RGB").quantize(palette=palette_img, dither=dither_mode)
        qw, qh = quantized.size
        bead_grid = quantized.load()

        # Count color usage
        counter = Counter()
        for y in range(qh):
            for x in range(qw):
                counter[bead_grid[x, y]] += 1

        # Merge similar colors
        if merge_value > 0:
            grid_flat = [bead_grid[x, y] for y in range(qh) for x in range(qw)]
            grid_flat, counter, color_entries, index_map, used_indices = _merge_similar_colors(
                grid_flat, counter, hex_list, color_entries, merge_value
            )
            if index_map:
                for y in range(qh):
                    for x in range(qw):
                        bead_grid[x, y] = grid_flat[y * qw + x]
                hex_list = [hex_list[i] for i in used_indices]

        # Replace colors (map original indices to filtered indices)
        if replace_colors:
            for src_str, tgt_orig in replace_colors.items():
                try:
                    src_orig = int(src_str)
                except (ValueError, TypeError):
                    continue
                src = orig_to_filtered.get(src_orig, src_orig)
                tgt = orig_to_filtered.get(tgt_orig, tgt_orig)
                if src < 0 or src >= len(hex_list) or tgt < 0 or tgt >= len(hex_list):
                    continue
                for y in range(qh):
                    for x in range(qw):
                        if bead_grid[x, y] == src:
                            bead_grid[x, y] = tgt
            counter = Counter()
            for y in range(qh):
                for x in range(qw):
                    counter[bead_grid[x, y]] += 1

        # --- Render grid image ---
        cell_size = 30
        label_left_width = 25 if show_coords else 5
        label_right_width = 25 if show_coords else 5
        label_bottom_height = 22 if show_coords else 5

        # Build colors_used first (needed for stats table)
        colors_used = []
        for i, count in sorted(counter.items(), key=lambda x: -x[1]):
            if i < len(color_entries) and count > 0:
                entry = color_entries[i]
                colors_used.append({
                    "hex": entry["hex"],
                    "name": entry["name"],
                    "code": entry["code"],
                    "index": i + 1,
                    "count": count,
                })
        total_beads = sum(c["count"] for c in colors_used)

        # Image dimensions
        font_cell = _get_font(max(8, cell_size // 3))
        font_label = _get_font(10)

        output_w = label_left_width + qw * cell_size + label_right_width
        grid_h = qh * cell_size + label_bottom_height
        output_h = grid_h
        output = Image.new("RGB", (output_w, output_h), "#FFFFFF")
        draw = ImageDraw.Draw(output)

        filtered_highlight = orig_to_filtered.get(highlight_index, -1)
        has_highlight = filtered_highlight >= 0 and filtered_highlight < len(hex_list)

        # Draw grid cells
        for y in range(qh):
            for x in range(qw):
                color_index = bead_grid[x, y]
                bg_hex = hex_list[color_index]
                x0 = label_left_width + x * cell_size
                y0 = y * cell_size
                x1 = x0 + cell_size
                y1 = y0 + cell_size

                draw.rectangle([x0, y0, x1, y1], fill=bg_hex)

                if show_grid:
                    draw.rectangle([x0, y0, x1, y1], outline="#CCCCCC", width=1)

                if has_highlight and color_index != filtered_highlight:
                    draw.rectangle([x0, y0, x1, y1], fill="#FFFFFF")
                    continue

                if has_highlight and color_index == filtered_highlight:
                    draw.rectangle([x0, y0, x1, y1], outline="#FF0000", width=2)

                # Draw color index number
                if color_index < len(color_entries):
                    code = color_entries[color_index]["code"]
                else:
                    code = str(color_index + 1)
                text_color = "#FFFFFF" if _is_dark(bg_hex) else "#000000"
                bbox = draw.textbbox((0, 0), code, font=font_cell)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                tx = x0 + (cell_size - tw) / 2
                ty = y0 + (cell_size - th) / 2
                draw.text((tx, ty), code, fill=text_color, font=font_cell)

        # Row numbers
        if show_coords:
            for y in range(qh):
                y0 = y * cell_size
                num = str(y + 1)
                bbox = draw.textbbox((0, 0), num, font=font_label)
                tw = bbox[2] - bbox[0]
                tx = (label_left_width - tw) / 2
                ty = y0 + (cell_size - 12) / 2
                draw.text((tx, ty), num, fill="#666666", font=font_label)
                tx = label_left_width + qw * cell_size + (label_right_width - tw) / 2
                draw.text((tx, ty), num, fill="#666666", font=font_label)

            for x in range(qw):
                x0 = label_left_width + x * cell_size
                num = str(x + 1)
                bbox = draw.textbbox((0, 0), num, font=font_label)
                tw = bbox[2] - bbox[0]
                tx = x0 + (cell_size - tw) / 2
                ty = qh * cell_size + (label_bottom_height - 12) / 2
                draw.text((tx, ty), num, fill="#666666", font=font_label)

        buffered = io.BytesIO()
        output.save(buffered, format="PNG")
        image_base64 = base64.b64encode(buffered.getvalue()).decode("ascii")

        return {
            "image_base64": image_base64,
            "grid_width": qw,
            "grid_height": qh,
            "colors_used": colors_used,
            "total_beads": total_beads,
            "palette_id": palette_id,
        }
