import io
import uuid
import barcode
from barcode.writer import ImageWriter


def generate_barcode_png(data: str) -> bytes:
    code = barcode.get('code128', data, writer=ImageWriter())
    buf = io.BytesIO()
    code.write(buf)
    return buf.getvalue()


def generate_unique_code() -> str:
    num = uuid.uuid4().int % 10**12
    return str(num).zfill(12)
