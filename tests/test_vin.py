# -*- coding: utf-8 -*-
"""Decodificador de VIN: VINs do mercado norte-americano trazem um código de tipo de mercado (letra no fim, ex. 8B9G)
que a KIS não registra — ela grava o tipo terminando em número (8B91/8B93/8B97). O decodificador resolve isso por
prefixo + mercado + fábrica; o câmbio não é afirmado a partir do GETR da KIS (é código de família) e o LCI de 2017
sai de fábrica como iDrive 5 com nota de atualização para o 6."""
import os, sys, unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from idemu import catalog, vin                            # noqa: E402


def typ(ebr='F30', ausf='ECE', mland='DEU', mot='B46B20O0'):
    return {'EBR': ebr, 'MARKE': 'BM', 'KFORM': 'LIM', 'MOT': mot, 'ANTR': 'RWD', 'AUSF': ausf,
            'MLAND': mland, 'ZYL': '4', 'HUBR': '1998', 'GETR': 'M', 'ms': 'F020'}   # GETR=M como na KIS do F30 automático


TYPES = {'8B91': typ(ausf='ECE', mland='DEU'),          # 330i sedã europeu
         '8B93': typ(ausf='US', mland='DEU'),           # 330i sedã EUA, Munique
         '8B97': typ(ausf='US', mland='ZAF'),           # 330i sedã EUA, Rosslyn — é o carro do teste
         '3A55': typ(ebr='E90', mot='N52B30')}          # para o caminho exato (VIN europeu)

NA_VIN = 'WBA8B9G59HNU51104'                            # 330i 2017 (descriptor de mercado 8B9G, fábrica N = Rosslyn)


def with_check(vin17):
    """Recalcula o dígito verificador (posição 9) para um VIN alterado."""
    return vin17[:8] + vin.check_digit(vin17) + vin17[9:]


def decode(v, types=TYPES):
    with mock.patch.object(vin, 'load_types', lambda *a, **k: types), \
         mock.patch.object(catalog, 'load_settings', lambda: {}):
        return vin.decode(v)


class MarketDescriptorTest(unittest.TestCase):
    def test_na_descriptor_falls_back_to_kis_variant(self):
        d = decode(NA_VIN)
        self.assertTrue(d['found'])
        self.assertEqual(d['chassis'], 'F30')
        self.assertEqual(d['approx'], '8B97')                      # MLAND=ZAF casa com a fábrica N do VIN
        self.assertTrue(d['us'])
        self.assertEqual(d['model_year'], 2017)
        self.assertTrue(d['check_digit_ok'])
        self.assertTrue(any('norte-americano' in n for n in d['notes']))

    def test_prefers_the_plant_when_known(self):
        v = with_check(NA_VIN[:10] + 'M' + NA_VIN[11:])            # mesma coisa, mas montado em Munique
        d = decode(v)
        self.assertEqual(d['approx'], '8B93')                      # MLAND=DEU

    def test_prefers_the_us_market(self):
        types = {k: v for k, v in TYPES.items() if k != '8B97'}    # só resta a variante europeia + Munique
        d = decode(with_check(NA_VIN[:10] + 'M' + NA_VIN[11:]))
        self.assertEqual(d['approx'], '8B93')                      # EUA vence o ECE
        self.assertTrue(d['us'])

    def test_exact_match_is_untouched(self):
        d = decode('WBA3A55090CM12345')                            # europeu: o código é o próprio tipo da KIS
        self.assertTrue(d['found'])
        self.assertNotIn('approx', d)
        self.assertEqual(d['kis_series'], 'F020')

    def test_unknown_type_keeps_the_old_note(self):
        d = decode(with_check('WBA9Z9Z59HNU51104'))
        self.assertFalse(d['found'])
        self.assertTrue(any('não está na base' in n for n in d['notes']))

    def test_environment_suggestion(self):
        env = decode(NA_VIN)['env']
        self.assertEqual(env['chassis'], 'F30')
        self.assertEqual(env['generation'], 'id5')
        self.assertEqual(env['coding']['language'], 'en_US')
        self.assertEqual(env['coding']['country'], 'US')
        self.assertEqual(env['coding']['hmi_version'], 'id5')

    def test_manual_is_not_claimed(self):
        d = decode(NA_VIN)
        self.assertEqual(d['gearbox'], '')                       # GETR=M na KIS é código de família, não "manual"
        self.assertEqual(vin.generation(d['chassis'], d['model_year']), 'id5')


class GenerationTest(unittest.TestCase):
    def test_id5_id6_by_model_year(self):
        self.assertEqual(vin.generation('F30', 2017), 'id5')     # LCI de 2017 saiu com iDrive 5 (iDrive 6 é atualização de software)
        self.assertEqual(vin.generation('F30', 2018), 'id6')
        self.assertEqual(vin.generation('G20', 2017), 'id7')     # as tabelas de geração vêm antes

    def test_na_vin_reports_id5_with_upgrade_note(self):
        d = decode(NA_VIN)
        self.assertEqual(d['generation'], 'id5')
        self.assertTrue(any('iDrive 6' in n for n in d['notes']))   # nota: atualização id5 → id6 existe


if __name__ == '__main__':
    unittest.main()
