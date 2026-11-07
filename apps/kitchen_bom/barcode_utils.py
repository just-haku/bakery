import barcode
from barcode.writer import SVGWriter
import base64
import io

def generate_barcode_svg(code_str: str) -> str:
    """
    Sinh chuỗi mã vạch Code128 dạng SVG dưới định dạng base64 Data URI
    Phù hợp để chèn trực tiếp vào thẻ <img src="..."> trong tem in
    """
    code_str = str(code_str).strip()
    if not code_str:
        code_str = "000000"

    try:
        code128_class = barcode.get_barcode_class('code128')
        writer = SVGWriter()
        bc = code128_class(code_str, writer=writer)
        buffer = io.BytesIO()
        bc.write(buffer, options={
            'module_width': 0.25,
            'module_height': 12.0,
            'font_size': 9,
            'text_distance': 3.0,
            'quiet_zone': 2.0,
            'write_text': True,
        })
        svg_bytes = buffer.getvalue()
        b64_encoded = base64.b64encode(svg_bytes).decode('utf-8')
        return f"data:image/svg+xml;base64,{b64_encoded}"
    except Exception as e:
        # Fallback SVG nếu có lỗi ký tự
        return ""
