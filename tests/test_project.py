"""Run: python -m unittest discover -s tests -v. No model downloads needed."""
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

TEST_DATA = tempfile.TemporaryDirectory(prefix='chromadam-test-')
os.environ['CHROMADAM_DATA'] = TEST_DATA.name

import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from backend.app import app
from backend.colors import extract_palette, contrast, color_share
from backend.ai import grabcut_mask, segment


def test_image():
    pixels = np.zeros((100, 100, 4), dtype=np.uint8)
    pixels[10:90, 10:58] = [255, 0, 0, 255]
    pixels[10:90, 58:90] = [0, 0, 255, 255]
    buffer = io.BytesIO()
    Image.fromarray(pixels).save(buffer, format='PNG')
    return buffer.getvalue()


class ColorTests(unittest.TestCase):
    def test_uniform_image_bypasses_segmentation(self):
        with patch('backend.ai.grabcut_mask', side_effect=AssertionError('Graph cut must not run')), patch('backend.ai.load_sam', side_effect=AssertionError('SAM must not run')):
            mask, method, score = segment(Image.new('RGB',(1000,1000),'green'))
        self.assertEqual(method,'Full image (uniform color)')
        self.assertTrue(mask.all())
        self.assertIsNone(score)

    def test_grabcut_graph_is_bounded_and_mask_size_preserved(self):
        sizes = []
        def fake_grabcut(image, mask, *args):
            sizes.append(image.shape[:2])
        rgb = np.zeros((1000, 1600, 3), dtype=np.uint8)
        with patch('backend.ai.cv2.grabCut', side_effect=fake_grabcut):
            mask = grabcut_mask(rgb, (800, 500))
        self.assertLessEqual(max(sizes[0]),384)
        self.assertEqual(mask.shape,(1000,1600))
        self.assertTrue(mask[500,800])

    def test_ratios_exclude_background(self):
        image = np.array(Image.open(io.BytesIO(test_image())))
        palette = extract_palette(image[:,:,:3], image[:,:,3]>127)
        self.assertEqual(len(palette), 2)
        self.assertAlmostEqual(palette[0]['percentage'], 60, places=3)
        self.assertAlmostEqual(palette[1]['percentage'], 40, places=3)
        self.assertAlmostEqual(sum(p['percentage'] for p in palette), 100, places=3)
        self.assertAlmostEqual(color_share(palette,'red'),60)
        self.assertAlmostEqual(color_share(palette,'#FF0000',1),60)

    def test_wcag_reference_pairs(self):
        self.assertEqual(contrast('#000000','#FFFFFF')['ratio'],21)
        self.assertEqual(contrast('#FFFFFF','#FFFFFF')['ratio'],1)
        self.assertFalse(contrast('#FFFFFF','#FFFFFF')['aa_large'])
        self.assertFalse(contrast('#777777','#FFFFFF')['aa_normal'])
        self.assertTrue(contrast('#767676','#FFFFFF')['aa_normal'])
        self.assertTrue(contrast('#000000','#FFFFFF')['aaa_normal'])


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.ctx = TestClient(app)
        self.client = self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None,None,None)

    def upload(self):
        response = self.client.post('/api/assets',files={'file':('two-colors.png',test_image(),'image/png')})
        self.assertEqual(response.status_code,201,response.text)
        return response.json()

    def test_upload_filter_export_edit_delete(self):
        asset = self.upload()
        aid = asset['id']
        self.assertEqual(asset['method'],'Image alpha')
        self.assertEqual(asset['coverage'],64)
        self.assertNotIn('embedding',asset)
        response=self.client.get('/api/assets',params={'color':'red','min_percentage':59})
        self.assertIn(aid,[a['id'] for a in response.json()['items']])
        response=self.client.get('/api/assets',params={'color':'red','min_percentage':61})
        self.assertNotIn(aid,[a['id'] for a in response.json()['items']])
        response=self.client.get('/api/assets',params={'q':'at least 61% red'})
        self.assertNotIn(aid,[a['id'] for a in response.json()['items']])
        self.assertEqual(self.client.get('/api/assets',params={'color':'#NOTHEX'}).status_code,422)
        self.assertEqual(self.client.get('/api/assets',params={'q':'at least 101% red'}).status_code,422)
        self.assertEqual(self.client.get('/api/contrast',params={'foreground':'oops','background':'#FFFFFF'}).status_code,422)
        self.client.patch(f'/api/assets/{aid}',json={'favorite':True,'tags':['shoe','campaign'],'name':'Campaign shoe'})
        response=self.client.get('/api/assets',params={'favorite':True})
        self.assertIn(aid,[a['id'] for a in response.json()['items']])
        export=self.client.get(f'/api/assets/{aid}/export').json()
        self.assertEqual(export['colors']['subject-1'],'#FF0000')
        self.assertIn('module.exports',self.client.get(f'/api/assets/{aid}/export?format=tailwind').text)
        self.assertIn('@theme',self.client.get(f'/api/assets/{aid}/export?format=css').text)
        self.assertEqual(self.client.get(asset['cutout_url']).status_code,200)
        self.assertEqual(self.client.get('/media/missing/original.png').status_code,404)
        self.assertEqual(self.client.get(f'/media/{aid}/unknown.png').status_code,422)
        self.assertEqual(self.client.delete(f'/api/assets/{aid}').status_code,204)
        self.assertEqual(self.client.get(f'/api/assets/{aid}').status_code,404)

    def test_invalid_uploads_and_metadata(self):
        response=self.client.post('/api/assets',files={'file':('x.png',b'not an image','image/png')})
        self.assertEqual(response.status_code,415)
        buffer=io.BytesIO();Image.new('RGB',(5,5)).save(buffer,format='PNG')
        self.assertEqual(self.client.post('/api/assets',files={'file':('tiny.png',buffer.getvalue(),'image/png')}).status_code,422)
        asset=self.upload()
        self.assertEqual(self.client.patch(f"/api/assets/{asset['id']}",json={'name':'   '}).status_code,422)
        self.assertEqual(self.client.post(f"/api/assets/{asset['id']}/segment",json={'x':2,'y':.5}).status_code,422)
        self.client.delete(f"/api/assets/{asset['id']}")


if __name__ == '__main__':
    unittest.main()
