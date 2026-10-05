"""Decupajul de ochi, identic la antrenare si la inferenta (altfel modelul vede alt tip de imagine).

Un ochi e descris de centru (cx, cy) si latime (distanta dintre colturi). Decupam un patrat cu
latura = SCALE * latime, centrat pe ochi, si il aducem la SIZE x SIZE pixeli. Cu `angle` putem
roti decupajul (ochiul inclinat cu capul devine orizontal).
"""
import cv2
import numpy as np

SIZE = 64
SCALE = 2.0  # latura decupajului = 2 x latimea ochiului: se vad pleoapele, sprancenele nu


def eye_patch(img_bgr, cx, cy, width, angle=0.0):
    side = max(width * SCALE, 8.0)
    k = SIZE / side
    # rotatie + scalare in jurul centrului ochiului, apoi mutam centrul in mijlocul decupajului
    m = cv2.getRotationMatrix2D((cx, cy), angle, k)
    m[0, 2] += SIZE / 2 - cx
    m[1, 2] += SIZE / 2 - cy
    out = cv2.warpAffine(img_bgr, m, (SIZE, SIZE), flags=cv2.INTER_AREA, borderMode=cv2.BORDER_REPLICATE)
    return cv2.cvtColor(out, cv2.COLOR_BGR2RGB)
