"""Glossário de coding (coding_gloss.json, NBT EVO Toolkit MIT): a junção por token com checagem de largura
e os rótulos de valor que ela corrige no editor. Sem emulador e sem firmware."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from idemu import coding  # noqa: E402


class JoinTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gloss = coding.load_gloss()

    def test_glossario_instalado(self):
        self.assertTrue(self.gloss, 'idemu/data/coding_gloss.json ausente (rode tools/build_coding_gloss.py)')
        self.assertGreater(len(self.gloss), 1000)      # o CAFD 00001EF6 cobre ~1321 dos 1366 parâmetros do editor

    def test_junao_real_rotulos_por_valor(self):
        """VIDEO_SPEEDLOCK_CONDITION: 3 bits no dicionário e no CAFD; o rótulo do toolkit vale."""
        g = coding._gloss_get('VIDEO_SPEEDLOCK_CONDITION', 3)
        self.assertIsNotNone(g)
        self.assertEqual(coding._gloss_value(g, 4), 'Parking brake or Park')

    def test_largura_diferente_descarta(self):
        """O mesmo token com outra largura de campo não é o mesmo parâmetro: sem glossário."""
        self.assertIsNone(coding._gloss_get('VIDEO_SPEEDLOCK_CONDITION', 4))

    def test_token_desconhecido(self):
        self.assertIsNone(coding._gloss_get('NAO_EXISTE_XPTO', 1))

    def test_arquivo_ausente_na_quebra(self):
        saved = coding._GLOSS
        try:
            coding._GLOSS = {}
            self.assertIsNone(coding.load_gloss())
            self.assertIsNone(coding._gloss_get('VIDEO_SPEEDLOCK_CONDITION', 3))
        finally:
            coding._GLOSS = saved


class OptionsTest(unittest.TestCase):
    ROWS = [{'value': 'va_RDC_nicht_aktiv', 'val': 0}, {'value': 'va_RDC', 'val': 1}, {'value': 'VariantVal', 'val': 0}]

    def test_rotulo_do_glossario_substitui_o_chute(self):
        opts = coding._options('RDC', self.ROWS, {'bits': 1, 'values': {'0': 'Off/inactive', '1': 'On/active'}})
        self.assertEqual([o['label'] for o in opts], ['Off/inactive', 'On/active'])

    def test_valor_sem_correspondencia_volta_ao_value_label(self):
        opts = coding._options('RDC', self.ROWS, {'bits': 1, 'values': {'0': 'Off/inactive'}})
        self.assertEqual(opts[1]['label'], 'Active')          # va_RDC sem sufixo = o parâmetro ligado

    def test_sem_glossario_comporta_atual(self):
        opts = coding._options('RDC', self.ROWS, None)
        self.assertEqual([o['label'] for o in opts], ['Not active', 'Active'])


if __name__ == '__main__':
    unittest.main()
