"""Optional real-model smoke test. Run after setup_models.py and make_samples.py."""
import os
from pathlib import Path
import sys
import time
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend import ai


def main():
    if not ai.status()['sam_ready'] or not ai.status()['clip_ready']:
        raise RuntimeError('Install the AI packages and model weights first.')
    started=time.perf_counter()
    image=Image.open(ROOT/'samples/crimson-running-shoe-opaque.jpg')
    truth=np.asarray(Image.open(ROOT/'samples/crimson-running-shoe.png'))[:,:,3]>127
    mask,method,predicted_iou=ai.segment(image)
    iou=float((mask&truth).sum()/(mask|truth).sum())
    assert method=='MobileSAM',ai.status()
    assert iou>.85,f'Synthetic foreground mask IoU too low: {iou}'
    vector=ai.embedding(image=image.convert('RGB'))
    assert vector is not None,ai.status()
    assert len(vector)==512
    assert abs(np.linalg.norm(vector)-1)<1e-5
    headphones=ai.embedding(image=Image.open(ROOT/'samples/lilac-headphones.png').convert('RGB'))
    text=ai.embedding(text='a red running shoe')
    assert headphones is not None and text is not None,ai.status()
    shoe_score=float(np.dot(vector,text)); headphones_score=float(np.dot(headphones,text))
    assert shoe_score>headphones_score,(shoe_score,headphones_score)
    point_mask,point_method,_=ai.segment(image,point=(400,390))
    assert point_method=='MobileSAM'
    assert .01<float(point_mask.mean())<.9
    print({'method':method,'synthetic_mask_iou':round(iou,4),'predicted_mask_iou':round(predicted_iou,4),
           'embedding_dimensions':len(vector),'embedding_norm':round(float(np.linalg.norm(vector)),6),
           'shoe_query_score':round(shoe_score,4),'headphones_query_score':round(headphones_score,4),
           'point_refinement':point_method,'total_seconds':round(time.perf_counter()-started,2)},flush=True)


if __name__=='__main__':
    main()
