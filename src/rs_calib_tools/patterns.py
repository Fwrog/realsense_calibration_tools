from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

import cv2
import numpy as np
import yaml
from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


DPI = 300
MM_PER_INCH = 25.4


def load_board_config(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def generate_all_patterns(board_config_paths: list[str | Path], output_dir: str | Path) -> list[Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    generated: list[Path] = []
    for config_path in board_config_paths:
        config = load_board_config(config_path)
        if config["type"] == "charuco":
            generated.extend(generate_charuco_a4(config, output_path))
        elif config["type"] == "checkerboard":
            generated.extend(generate_checkerboard_a4(config, output_path))
        elif config["type"] == "aruco_marker_sheet":
            generated.extend(generate_aruco_marker_sheet_a4(config, output_path))
        else:
            raise ValueError(f"Unsupported board type: {config['type']}")

    print("Generated printable patterns:")
    for path in generated:
        print(f"  - {path}")
    print("Print PDFs at 100% actual size. Do not use fit-to-page.")
    print("Measure printed square/marker sizes and update YAML configs if needed.")
    return generated


def generate_charuco_a4(config: dict, output_dir: Path) -> list[Path]:
    board_id = config["board_id"]
    page = _blank_page(config)

    square_px = _mm_to_px(float(config["square_size_mm_nominal"]))
    board_width_px = int(config["squares_x"]) * square_px
    board_height_px = int(config["squares_y"]) * square_px

    board = _create_charuco_board_pixels(config)
    board_image = _render_charuco_board(board, (board_width_px, board_height_px))
    board_pil = Image.fromarray(board_image).convert("L")
    _paste_centered(page, board_pil)

    png_path = output_dir / f"{board_id}.png"
    pdf_path = output_dir / f"{board_id}.pdf"
    svg_path = output_dir / f"{board_id}.svg"
    _save_png_pdf_svg(page, config, png_path, pdf_path, svg_path)
    return [svg_path, pdf_path, png_path]


def generate_checkerboard_a4(config: dict, output_dir: Path) -> list[Path]:
    board_id = config["board_id"]
    page = _blank_page(config)
    square_px = _mm_to_px(float(config["square_size_mm_nominal"]))
    squares_x = int(config["squares_x"])
    squares_y = int(config["squares_y"])

    board = Image.new("L", (squares_x * square_px, squares_y * square_px), 255)
    draw = ImageDraw.Draw(board)
    for y in range(squares_y):
        for x in range(squares_x):
            if (x + y) % 2 == 0:
                x0 = x * square_px
                y0 = y * square_px
                draw.rectangle([x0, y0, x0 + square_px - 1, y0 + square_px - 1], fill=0)

    _paste_centered(page, board)

    png_path = output_dir / f"{board_id}.png"
    pdf_path = output_dir / f"{board_id}.pdf"
    svg_path = output_dir / f"{board_id}.svg"
    _save_png_pdf_svg(page, config, png_path, pdf_path, svg_path)
    return [svg_path, pdf_path, png_path]


def generate_aruco_marker_sheet_a4(config: dict, output_dir: Path) -> list[Path]:
    board_id = config["board_id"]
    page = _blank_page(config).convert("RGB")
    draw = ImageDraw.Draw(page)

    marker_ids = [int(value) for value in config["marker_ids"]]
    marker_px = _mm_to_px(float(config["marker_size_mm_nominal"]))
    spacing_px = _mm_to_px(float(config["spacing_mm"]))
    columns = 2
    rows = int(np.ceil(len(marker_ids) / columns))
    grid_w = columns * marker_px + (columns - 1) * spacing_px
    grid_h = rows * marker_px + (rows - 1) * spacing_px
    start_x = (page.width - grid_w) // 2
    start_y = (page.height - grid_h) // 2

    dictionary = _aruco_dictionary(config["dictionary"])
    for index, marker_id in enumerate(marker_ids):
        row = index // columns
        col = index % columns
        x = start_x + col * (marker_px + spacing_px)
        y = start_y + row * (marker_px + spacing_px)
        marker = _draw_marker(dictionary, marker_id, marker_px)
        page.paste(Image.fromarray(marker).convert("RGB"), (x, y))
        draw.text((x, y + marker_px + 8), f"ID {marker_id}", fill=(0, 0, 0))

    png_path = output_dir / f"{board_id}.png"
    pdf_path = output_dir / f"{board_id}.pdf"
    svg_path = output_dir / f"{board_id}.svg"
    _save_png_pdf_svg(page.convert("L"), config, png_path, pdf_path, svg_path)
    return [svg_path, pdf_path, png_path]


def _create_charuco_board_pixels(config: dict):
    aruco = cv2.aruco
    dictionary = _aruco_dictionary(config["dictionary"])
    square = float(config["square_size_mm_nominal"])
    marker = float(config["marker_size_mm_nominal"])
    squares_x = int(config["squares_x"])
    squares_y = int(config["squares_y"])

    if hasattr(aruco, "CharucoBoard"):
        try:
            return aruco.CharucoBoard((squares_x, squares_y), square, marker, dictionary)
        except TypeError:
            pass
    if hasattr(aruco, "CharucoBoard_create"):
        return aruco.CharucoBoard_create(squares_x, squares_y, square, marker, dictionary)
    raise RuntimeError("OpenCV aruco module does not provide ChArUco board support.")


def _render_charuco_board(board, size: tuple[int, int]) -> np.ndarray:
    if hasattr(board, "generateImage"):
        image = board.generateImage(size)
    elif hasattr(board, "draw"):
        image = board.draw(size)
    else:
        raise RuntimeError("OpenCV ChArUco board cannot render this target.")
    return np.asarray(image)


def _aruco_dictionary(name: str):
    aruco = cv2.aruco
    if not hasattr(aruco, name):
        raise RuntimeError(f"Unknown OpenCV ArUco dictionary: {name}")
    dictionary_id = getattr(aruco, name)
    if hasattr(aruco, "getPredefinedDictionary"):
        return aruco.getPredefinedDictionary(dictionary_id)
    return aruco.Dictionary_get(dictionary_id)


def _draw_marker(dictionary, marker_id: int, side_px: int) -> np.ndarray:
    aruco = cv2.aruco
    if hasattr(aruco, "generateImageMarker"):
        return aruco.generateImageMarker(dictionary, marker_id, side_px)
    marker = np.full((side_px, side_px), 255, dtype=np.uint8)
    aruco.drawMarker(dictionary, marker_id, side_px, marker, 1)
    return marker


def _blank_page(config: dict) -> Image.Image:
    width_px = _mm_to_px(float(config["page_width_mm"]))
    height_px = _mm_to_px(float(config["page_height_mm"]))
    return Image.new("L", (width_px, height_px), 255)


def _paste_centered(page: Image.Image, child: Image.Image) -> None:
    left = (page.width - child.width) // 2
    top = (page.height - child.height) // 2
    page.paste(child, (left, top))


def _mm_to_px(mm_value: float) -> int:
    return max(1, int(round(mm_value / MM_PER_INCH * DPI)))


def _save_png_pdf_svg(page: Image.Image, config: dict, png_path: Path, pdf_path: Path, svg_path: Path) -> None:
    page.save(png_path, dpi=(DPI, DPI))
    _save_svg_from_bitmap(page, config, svg_path)

    # The PDF page is A4 in physical units; the bitmap already contains the
    # required white margins, so drawing it full-page preserves print geometry.
    pdf = canvas.Canvas(str(pdf_path), pagesize=A4)
    pdf.drawImage(str(png_path), 0, 0, width=A4[0], height=A4[1])
    pdf.showPage()
    pdf.save()


def _save_svg_from_bitmap(page: Image.Image, config: dict, svg_path: Path) -> None:
    width_mm = float(config["page_width_mm"])
    height_mm = float(config["page_height_mm"])
    gray = np.asarray(page.convert("L"))
    black = gray < 128
    px_to_mm_x = width_mm / gray.shape[1]
    px_to_mm_y = height_mm / gray.shape[0]

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_mm:g}mm" '
            f'height="{height_mm:g}mm" viewBox="0 0 {width_mm:g} {height_mm:g}">'
        ),
        f'  <title>{escape(str(config["board_id"]))}</title>',
        '  <rect x="0" y="0" width="100%" height="100%" fill="white"/>',
        '  <g fill="black" shape-rendering="crispEdges">',
    ]

    # Convert binary page pixels into horizontal SVG runs. This keeps the SVG
    # physically sized in millimetres without depending on OpenCV's external
    # pattern-tools repository.
    for y, row in enumerate(black):
        x = 0
        while x < row.size:
            if not row[x]:
                x += 1
                continue
            start = x
            while x < row.size and row[x]:
                x += 1
            lines.append(
                "    "
                f'<rect x="{start * px_to_mm_x:.4f}" y="{y * px_to_mm_y:.4f}" '
                f'width="{(x - start) * px_to_mm_x:.4f}" height="{px_to_mm_y:.4f}"/>'
            )

    lines.extend(["  </g>", "</svg>", ""])
    svg_path.write_text("\n".join(lines), encoding="utf-8")
