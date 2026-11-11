# -*- coding: utf-8 -*-
"""Extensões de host (idemu/plugins.py): o pacote vem de fora, então o desempacotamento e o
serviço de arquivos têm travas; e um pacote quebrado nunca derruba a lista dos demais."""
import json, os, stat, sys, tempfile, unittest, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from idemu import plugins                                   # noqa: E402

MANIFEST = {'name': 'Demo', 'version': '1.0', 'scripts': ['main.js'], 'styles': ['style.css']}


def zip_write(path, files):
    """files: {caminho_no_zip: bytes}. """
    with zipfile.ZipFile(path, 'w') as zf:
        for name, data in files.items():
            zf.writestr(name, data)


def demo_zip(path, manifest=None, extra=None):
    files = {'plugin.json': json.dumps(MANIFEST if manifest is None else manifest),
             'main.js': b'IDE.registerTab({id:"demo"});', 'style.css': b'.demo{}'}
    files.update(extra or {})
    zip_write(path, files)


class ScanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name
        self.addCleanup(self.tmp.cleanup)

    def scan(self):
        plugins.scan(base=self.base)
        return plugins.public(), plugins.problems()

    def test_zip_happy_path(self):
        demo_zip(os.path.join(self.base, 'demo.zip'))
        ok, bad = self.scan()
        self.assertEqual([p['id'] for p in ok], ['demo'])
        self.assertEqual(ok[0]['name'], 'Demo')
        self.assertEqual(ok[0]['scripts'], ['main.js'])
        self.assertEqual(ok[0]['styles'], ['style.css'])
        self.assertIsNone(ok[0]['error'])
        self.assertEqual(bad, [])
        p = plugins.file_for('demo', 'main.js')
        self.assertTrue(p and os.path.isfile(p))
        self.assertIn('.installed', p)

    def test_public_has_no_private_paths(self):
        demo_zip(os.path.join(self.base, 'demo.zip'))
        ok, _ = self.scan()
        for item in ok + plugins.problems():
            self.assertNotIn('pdir', item)
            self.assertNotIn('dir', item)

    def test_zip_slip_rejected(self):
        demo_zip(os.path.join(self.base, 'evil.zip'), extra={'../vizinho.txt': b'x'})
        ok, bad = self.scan()
        self.assertEqual(ok, [])
        self.assertIn('rejeitado', bad[0]['error'])
        self.assertFalse(os.path.exists(os.path.join(self.base, '..', 'vizinho.txt')))

    def test_symlink_member_rejected(self):
        path = os.path.join(self.base, 'link.zip')
        with zipfile.ZipFile(path, 'w') as zf:
            zf.writestr('plugin.json', json.dumps(MANIFEST))
            zi = zipfile.ZipInfo('evil')
            zi.external_attr = (stat.S_IFLNK | 0o777) << 16
            zf.writestr(zi, '/etc/passwd')
        ok, bad = self.scan()
        self.assertEqual(ok, [])
        self.assertIn('simb', bad[0]['error'])

    def test_zip_with_wrapper_folder(self):
        zip_write(os.path.join(self.base, 'wrap.zip'),
                  {'minha-ferramenta/plugin.json': json.dumps(dict(MANIFEST, id='minha-ferramenta')),
                   'minha-ferramenta/main.js': b'// ok', 'minha-ferramenta/style.css': b'.x{}'})
        ok, bad = self.scan()
        self.assertEqual([p['id'] for p in ok], ['minha-ferramenta'])
        self.assertEqual(bad, [])
        self.assertTrue(plugins.file_for('minha-ferramenta', 'main.js'))
        self.assertFalse(os.path.exists(os.path.join(self.base, '.installed', 'minha-ferramenta', 'minha-ferramenta')))  # o prefixo do ZIP é removido

    def test_zip_without_manifest_is_ignored(self):
        zip_write(os.path.join(self.base, 'fotos.zip'), {'ferias.jpg': b'x'})
        ok, bad = self.scan()
        self.assertEqual((ok, bad), ([], []))

    def test_bad_zip_reports_problem(self):
        open(os.path.join(self.base, 'quebrado.zip'), 'wb').write(b'nem comeca em PK')
        ok, bad = self.scan()
        self.assertEqual(ok, [])
        self.assertEqual(bad[0]['error'], 'ZIP inválido')

    def test_bad_manifest_id(self):
        demo_zip(os.path.join(self.base, 'id.zip'), manifest=dict(MANIFEST, id='Tool Mal Id!'))
        ok, bad = self.scan()
        self.assertEqual(ok, [])
        self.assertIn('id inválido', bad[0]['error'])

    def test_duplicate_id(self):
        demo_zip(os.path.join(self.base, 'a.zip'), manifest=dict(MANIFEST, id='demo'))
        demo_zip(os.path.join(self.base, 'b.zip'), manifest=dict(MANIFEST, id='demo'))
        ok, bad = self.scan()
        self.assertEqual([p['id'] for p in ok], ['demo'])
        self.assertIn('repetido', bad[0]['error'])

    def test_missing_script(self):
        demo_zip(os.path.join(self.base, 'falta.zip'), manifest={'scripts': ['sumido.js']})
        ok, bad = self.scan()
        self.assertEqual(ok, [])
        self.assertIn('falta', bad[0]['error'])

    def test_loose_folder(self):
        d = os.path.join(self.base, 'solta')
        os.makedirs(d)
        open(os.path.join(d, 'plugin.json'), 'w').write(json.dumps({'name': 'Solta'}))
        open(os.path.join(d, 'a.js'), 'w').write('')
        open(os.path.join(d, 'b.js'), 'w').write('')
        ok, bad = self.scan()
        self.assertEqual([p['id'] for p in ok], ['solta'])
        self.assertEqual(ok[0]['scripts'], ['a.js', 'b.js'])          # sem manifest: todos os .js da raiz
        self.assertEqual(bad, [])

    def test_loose_folder_without_manifest_ignored(self):
        os.makedirs(os.path.join(self.base, 'qualquer'))
        self.assertEqual(self.scan(), ([], []))

    def test_reextract_when_zip_changes(self):
        path = os.path.join(self.base, 'demo.zip')
        demo_zip(path)
        self.scan()
        self.assertIn('IDE.registerTab', open(plugins.file_for('demo', 'main.js'), 'rb').read().decode())
        demo_zip(path, extra={'main.js': b'// versao nova'})          # writestr por nome substitui o conteúdo (tamanho muda)
        ok, _ = self.scan()
        self.assertEqual([p['id'] for p in ok], ['demo'])
        self.assertIn('versao nova', open(plugins.file_for('demo', 'main.js'), 'rb').read().decode())

    def test_missing_base_folder(self):
        plugins.scan(base=os.path.join(self.base, 'nao-existe'))
        self.assertEqual(plugins.public(), [])


class FileForTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name
        demo_zip(os.path.join(self.tmp.name, 'demo.zip'))
        plugins.scan(base=self.base)
        self.addCleanup(self.tmp.cleanup)

    def test_traversal_blocked(self):
        for rel in ('../plugin.json', 'a/../../etc/passwd', '/etc/passwd', 'C:\\windows', '..', ''):
            self.assertIsNone(plugins.file_for('demo', rel), rel)

    def test_directory_not_served(self):
        self.assertIsNone(plugins.file_for('demo', ''))

    def test_unknown_id(self):
        self.assertIsNone(plugins.file_for('ninguem', 'main.js'))

    def test_broken_plugin_not_served(self):
        demo_zip(os.path.join(self.base, 'segundo.zip'), manifest=dict(MANIFEST, id='demo'))   # id repetido: fica fora
        plugins.scan(base=self.base)
        self.assertTrue(plugins.file_for('demo', 'main.js'))       # o primeiro continua valendo


class PythonHookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(lambda: [sys.modules.pop('idemu_plugin_' + i, None) for i in ('hookok', 'hookruim')])

    def test_register_runs(self):
        zip_write(os.path.join(self.base, 'ok.zip'), {
            'plugin.json': json.dumps({'id': 'hookok', 'python': 'srv.py'}),
            'srv.py': 'def register(api):\n    open(api.dir + "/.hooked", "w").write(api.id)\n'})
        plugins.scan(base=self.base)
        self.assertEqual([p['id'] for p in plugins.public()], ['hookok'])
        self.assertEqual(plugins.problems(), [])
        self.assertEqual(open(plugins.file_for('hookok', '.hooked')).read(), 'hookok')
    def test_broken_register_only_kills_the_plugin(self):
        zip_write(os.path.join(self.base, 'ruim.zip'), {
            'plugin.json': json.dumps({'id': 'hookruim', 'python': 'srv.py'}),
            'srv.py': 'raise RuntimeError("explodeu")\n'})
        demo_zip(os.path.join(self.base, 'demo.zip'))
        plugins.scan(base=self.base)
        self.assertEqual([p['id'] for p in plugins.public()], ['demo'])
        self.assertIn('python:', plugins.problems()[0]['error'])


class MemberCheckTest(unittest.TestCase):
    def test_accepts(self):
        for rel in ('a.js', 'lib/a.js', 'dir/sub/x.bin', 'a-b_c.js'):
            self.assertEqual(plugins._check_member(rel), rel)

    def test_rejects(self):
        for rel in ('../a', 'a/../../b', '/etc/passwd', 'C:/windows/x', '', 'dir/', './a/../..'):
            self.assertIsNone(plugins._check_member(rel), rel)

    def test_cleaning_is_safe(self):
        self.assertEqual(plugins._check_member('./a//b.js'), 'a/b.js')
        self.assertEqual(plugins._check_member('a\\..\\b'), None)


if __name__ == '__main__':
    unittest.main()
