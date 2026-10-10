"""Fictional PDFs for deterministic tests; never an actual PAES exam."""
from pathlib import Path


def pdf(path, streams):
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'', b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    kids = []
    for text in streams:
        page_id = len(objects) + 1; stream_id = page_id + 1; kids.append(f'{page_id} 0 R')
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 400] /Resources << /Font << /F1 3 0 R >> >> /Contents {stream_id} 0 R >>'.encode())
        content = text.encode('ascii')
        objects.append(b'<< /Length ' + str(len(content)).encode() + b' >>\nstream\n' + content + b'\nendstream')
    objects[1] = f'<< /Type /Pages /Count {len(kids)} /Kids [{" ".join(kids)}] >>'.encode()
    payload = bytearray(b'%PDF-1.4\n'); offsets = [0]
    for index, item in enumerate(objects, 1):
        offsets.append(len(payload)); payload.extend(f'{index} 0 obj\n'.encode() + item + b'\nendobj\n')
    xref = len(payload)
    payload.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]: payload.extend(f'{offset:010d} 00000 n \n'.encode())
    payload.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    Path(path).write_bytes(payload)


def create(folder):
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    pdf(folder / 'synthetic-m1.pdf', [
        'BT /F1 12 Tf 20 370 Td (SYNTHETIC M1 - 2 questions) Tj 0 -30 Td (1. What is 2+2? A. 3 B. 4) Tj ET 40 200 100 80 re S 40 240 m 140 240 l S',
        'BT /F1 12 Tf 20 370 Td (2. What is 3+1? A. 3 B. 4) Tj ET 40 200 100 80 re S'])
    pdf(folder / 'synthetic-key.pdf', ['BT /F1 12 Tf 20 370 Td (SYNTHETIC M1 answer key: 1 B, 2 B) Tj ET'])
    return folder / 'synthetic-m1.pdf', folder / 'synthetic-key.pdf'

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(); p.add_argument('--output', required=True); args = p.parse_args()
    print(create(args.output))
