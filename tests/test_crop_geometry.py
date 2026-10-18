"""Pixel comparisons for visible PDF coordinates, including rotated pages."""
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageChops
import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'shared/scripts'))
sys.path.insert(0, str(ROOT/'examples'))
from lab import configure_workspace
from pdf_assets import render_crop
import synthetic


class CropGeometryTests(unittest.TestCase):
    def test_visible_crop_matches_full_page_pixels_at_every_rotation(self):
        (ROOT/'tmp').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temporary:
            home = Path(temporary)
            configure_workspace(home)
            source = home/'fictional.pdf'
            synthetic.pdf(source, ['BT /F1 12 Tf 20 370 Td (Label C) Tj ET 20 200 100 100 re S'])
            source.write_bytes(source.read_bytes().replace(b'/MediaBox [0 0 400 400]', b'/MediaBox [0 0 300 500]'))
            with pdfium.PdfDocument(str(source)) as document:
                page = document[0]
                try:
                    for rotation in (0, 90, 180, 270):
                        with self.subTest(rotation=rotation):
                            page.set_rotation(rotation)
                            width, height = page.get_size()
                            box = [5, 7, width-5, height-7]
                            render_crop(page, home/'full.png', scale=2)
                            render_crop(page, home/'crop.png', box, scale=2)
                            with Image.open(home/'full.png') as full, Image.open(home/'crop.png') as crop:
                                expected = full.crop(tuple(int(v*2) for v in box))
                                self.assertEqual(crop.size, expected.size)
                                self.assertIsNone(ImageChops.difference(crop, expected).getbbox())
                finally: page.close()


if __name__ == '__main__': unittest.main()
