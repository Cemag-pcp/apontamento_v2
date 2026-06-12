from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class ComprasScrollSuperiorTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.compras_dir = Path(settings.BASE_DIR) / "compras"

    def test_scroll_superior_existe_apenas_na_analise_direta(self):
        analise = (
            self.compras_dir / "templates" / "compras" / "analise.html"
        ).read_text(encoding="utf-8")
        indireto = (
            self.compras_dir / "templates" / "compras" / "mat_indireto.html"
        ).read_text(encoding="utf-8")

        self.assertIn('id="comprasTableScrollTop"', analise)
        self.assertIn('id="comprasTableScrollTopContent"', analise)
        self.assertNotIn('id="comprasTableScrollTop"', indireto)

    def test_javascript_sincroniza_e_redimensiona_scroll_superior(self):
        script = (
            self.compras_dir / "static" / "js" / "compras.js"
        ).read_text(encoding="utf-8")

        self.assertIn("tableWrap.scrollLeft = scrollTop.scrollLeft", script)
        self.assertIn("scrollTop.scrollLeft = tableWrap.scrollLeft", script)
        self.assertIn("new ResizeObserver", script)
        self.assertIn("possuiOverflowHorizontal", script)
        self.assertIn("agendarAtualizacaoScrollSuperior();", script)
