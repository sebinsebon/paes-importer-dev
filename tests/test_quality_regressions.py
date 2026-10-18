"""Regression cases from real-looking M1 serialization failures (fictional fixtures)."""
import sys
import unittest
from pathlib import Path

from support import RUNTIME_ROOT as ROOT, DEV_ROOT, WORK_ROOT
sys.path.insert(0, str(ROOT / "shared" / "scripts"))
from package_io import validate_structured_content, renderable_math


def question(stem=None, options=None):
    return {
        "id": "fictional-q1",
        "stem": stem if stem is not None else [{"type": "text", "text": "Pregunta de prueba."}],
        "options": options if options is not None else [
            {"label": "A", "blocks": [{"type": "text", "text": "1"}]},
            {"label": "B", "blocks": [{"type": "text", "text": "2"}]},
        ],
        "explanation": {"blocks": []},
    }


class ImportQualityGateTests(unittest.TestCase):
    def test_double_escaped_sqrt_rejected(self):
        q = question(stem=[{"type": "math", "latex": r"-2\\sqrt{3}", "display": False}])
        with self.assertRaisesRegex(ValueError, "DOUBLE_ESCAPED_LATEX_COMMAND"):
            validate_structured_content(q)

    def test_normal_sqrt_and_case_row_separator_allowed(self):
        q = question(stem=[
            {"type": "math", "latex": r"-2\sqrt{3}", "display": False},
            {"type": "math", "latex": r"\begin{cases}x=2\\y=3\end{cases}", "display": True},
        ])
        validate_structured_content(q)

    def test_truncated_monetary_options_rejected(self):
        opts = [
            {"label": label, "blocks": [{"type": "text", "text": " 000"}]}
            for label in ("A", "B", "C", "D")
        ]
        with self.assertRaisesRegex(ValueError, "TRUNCATED_NUMERIC_OPTIONS"):
            validate_structured_content(question(options=opts))

    def test_real_monetary_options_allowed(self):
        opts = [
            {"label": label, "blocks": [{"type": "text", "text": value}]}
            for label, value in (("A", "$11 000"), ("B", "$12 000"))
        ]
        validate_structured_content(question(options=opts))

    def test_visual_option_placeholder_rejected(self):
        opts = [
            {"label": "A", "blocks": [{"type": "text", "text": "Gráfico de la alternativa A"}]},
            {"label": "B", "blocks": [{"type": "text", "text": "Gráfico de la alternativa B"}]},
        ]
        with self.assertRaisesRegex(ValueError, "VISUAL_OPTION_PLACEHOLDER"):
            validate_structured_content(question(options=opts))

    def test_currency_multiple_amounts_allowed(self):
        validate_structured_content(question(stem=[{'type':'text','text':'Cuesta $ 11 000 y cuesta $ 80 000.'}]))

    def test_blank_text_rejected(self):
        with self.assertRaisesRegex(ValueError,'EMPTY_CONTENT'):
            validate_structured_content(question(stem=[{'type':'text','text':'   '}]))

    def test_display_tag_validated_with_mode(self):
        renderable_math(((r'\tag{1}x=2', True),))
        with self.assertRaisesRegex(ValueError,'KaTeX'):
            renderable_math(((r'\tag{1}x=2', False),))

    def test_aligned_row_separator_before_variable_allowed(self):
        validate_structured_content(question(stem=[{'type':'math','latex':r'\begin{aligned}x=2\\sin(x)=0\end{aligned}','display':True}]))

    def test_double_vec_outside_environment_rejected(self):
        with self.assertRaisesRegex(ValueError,'DOUBLE_ESCAPED'):
            validate_structured_content(question(stem=[{'type':'math','latex':r'\\vec{x}','display':False}]))

    def test_visual_option_image_allowed(self):
        opts = [
            {"label": "A", "blocks": [{"type": "image", "asset_id": "fig-a", "alt": "Gráfico A"}]},
            {"label": "B", "blocks": [{"type": "image", "asset_id": "fig-b", "alt": "Gráfico B"}]},
        ]
        validate_structured_content(question(options=opts))


if __name__ == "__main__":
    unittest.main()
