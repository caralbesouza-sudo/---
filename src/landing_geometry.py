"""Landing strip geometry for calibrated 1280 x 720 battle screenshots.

The striped boundary is only a candidate: a wide clear apron on its sea side
and water beyond that apron must both be visible. UI pixels cannot be targets.
"""
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class LandingZone:
    point: tuple
    polygon: tuple
    score: float


def scene_masks(screen):
    hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    allowed = np.ones(h.shape, dtype=np.uint8)
    allowed[:85] = 0
    allowed[:, :180] = 0
    allowed[:, 1180:] = 0
    allowed[510:, :420] = 0
    allowed[475:, 875:] = 0
    allowed[600:] = 0
    # Details panel's pale blue background; masked only when actually present.
    panel = hsv[105:330, 935:1245]
    if panel.size and np.mean((panel[:, :, 0] >= 100) &
                              (panel[:, :, 0] <= 125) &
                              (panel[:, :, 1] < 90) &
                              (panel[:, :, 2] > 200)) > 0.35:
        allowed[90:345, 920:] = 0
    yellow = ((h >= 18) & (h <= 40) & (s >= 60) & (v >= 130) & (allowed > 0))
    gray = ((s < 65) & (v >= 100) & (v <= 235) & (allowed > 0))
    water = ((h >= 85) & (h <= 120) & (s >= 70) & (v >= 45) & (v <= 235))
    return yellow.astype(np.uint8) * 255, gray, water, allowed


def sample_band(mask, origin, tangent, normal, along, depth):
    pts = origin + np.asarray(along)[:, None, None] * tangent + np.asarray(depth)[None, :, None] * normal
    xy = np.rint(pts).astype(int)
    valid = ((xy[:, :, 0] >= 0) & (xy[:, :, 0] < mask.shape[1]) &
             (xy[:, :, 1] >= 0) & (xy[:, :, 1] < mask.shape[0]))
    values = np.zeros(valid.shape, dtype=bool)
    values[valid] = mask[xy[:, :, 1][valid], xy[:, :, 0][valid]] > 0
    return values


def has_clear_landing_patch(point, gray, allowed):
    px, py = point
    if not (10 <= px < gray.shape[1] - 10 and 10 <= py < gray.shape[0] - 10):
        return False
    patch = gray[py-10:py+11, px-10:px+11]
    clickable = allowed[py-10:py+11, px-10:px+11]
    return bool(clickable.all() and patch.mean() >= 0.90)


def find_landing_zone(screen, preferred_point=None):
    """Revalidate a previous point against CURRENT geometry before choosing a new one.

    Scores vary with waves and Hough segments. A higher score elsewhere on the
    same apron is not evidence that the previous valid point moved.
    """
    if screen.shape[:2] != (720, 1280):
        return None
    yellow, gray, water, allowed = scene_masks(screen)
    lines = cv2.HoughLinesP(yellow, 1, np.pi / 360, threshold=65,
                           minLineLength=140, maxLineGap=30)
    if lines is None:
        return None
    best = None
    best_rank = -1
    tracked = None
    tracked_margin = -1
    can_track = preferred_point is not None and has_clear_landing_patch(preferred_point, gray, allowed)
    for x1, y1, x2, y2 in lines[:, 0]:
        start = np.array([x1, y1], dtype=float)
        end = np.array([x2, y2], dtype=float)
        if end[0] < start[0]:
            start, end = end, start
        length = np.linalg.norm(end - start)
        tangent = (end - start) / length
        if abs(tangent[1]) > 0.75:
            continue
        normal = np.array([-tangent[1], tangent[0]])
        # Evaluate local contiguous strips. One end may be behind the details UI.
        for offset in np.arange(0, max(1, length - 139), 30):
            origin = start + tangent * offset
            along = np.arange(10, 141, 5)
            gray_support = sample_band(gray, origin, tangent, normal, along, np.arange(18, 66, 4)).mean()
            water_support = sample_band(water & (allowed > 0), origin, tangent, normal,
                                        along, np.arange(105, 186, 8)).mean()
            stripe_support = sample_band(yellow, origin, tangent, normal,
                                         along, [-3, 0, 3]).mean()
            if gray_support < 0.80 or water_support < 0.28 or stripe_support < 0.20:
                continue
            # Keep a generous margin inside the visible apron, away from waves
            # and the striped boundary. Validate a disk, not just one gray pixel.
            point = np.rint(origin + tangent * 75 + normal * 40).astype(int)
            if not has_clear_landing_patch(point, gray, allowed):
                continue
            polygon = tuple(tuple(int(v) for v in np.rint(origin + tangent * a + normal * d))
                            for a, d in [(10, 18), (140, 18), (140, 65), (10, 65)])
            rank = gray_support + water_support + stripe_support * 0.3
            score = float(min(0.99, 0.70 + 0.15 * gray_support + 0.10 * water_support))
            if can_track:
                margin = cv2.pointPolygonTest(np.asarray(polygon, dtype=np.int32),
                                             tuple(float(v) for v in preferred_point), True)
                # The whole click footprint must stay inside a freshly verified
                # strip. Being gray alone, or near the old point, is insufficient.
                if margin >= 12 and margin > tracked_margin:
                    tracked = LandingZone(tuple(int(v) for v in preferred_point), polygon, score)
                    tracked_margin = margin
            if rank > best_rank:
                best = LandingZone(tuple(int(v) for v in point), polygon, score)
                best_rank = rank
    return tracked if tracked is not None else best


def recover_occluded_zone(screen, reference_screen, reference_zone, preferred_point=None):
    """Locate a clear point INSIDE a previously verified apron after boats arrive.

    This is only for deployment rechecks. RANSAC scene registration must prove
    that the reference still describes this battlefield; no blind old-point reuse.
    """
    if screen.shape[:2] != (720, 1280) or reference_screen.shape != screen.shape:
        return None
    _, gray, _, allowed = scene_masks(screen)
    _, _, _, reference_allowed = scene_masks(reference_screen)
    feature_mask = np.zeros((720, 1280), np.uint8)
    feature_mask[85:420, 200:900] = 255
    feature_mask[(allowed == 0) | (reference_allowed == 0)] = 0
    orb = cv2.ORB_create(nfeatures=1800)
    old_keys, old_desc = orb.detectAndCompute(cv2.cvtColor(reference_screen, cv2.COLOR_BGR2GRAY), feature_mask)
    new_keys, new_desc = orb.detectAndCompute(cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY), feature_mask)
    if old_desc is None or new_desc is None or len(new_desc) < 2:
        return None
    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(old_desc, new_desc, k=2)
    good = [pair[0] for pair in pairs if len(pair) == 2 and pair[0].distance < 0.72 * pair[1].distance]
    if len(good) < 20:
        return None
    old = np.float32([old_keys[m.queryIdx].pt for m in good])
    new = np.float32([new_keys[m.trainIdx].pt for m in good])
    transform, inliers = cv2.estimateAffinePartial2D(old, new, method=cv2.RANSAC, ransacReprojThreshold=2)
    if transform is None or inliers is None or inliers.sum() < 20 or inliers.mean() < 0.65:
        return None
    spread = np.ptp(old[inliers.ravel() > 0], axis=0)
    scale = np.hypot(transform[0, 0], transform[1, 0])
    angle = np.degrees(np.arctan2(transform[1, 0], transform[0, 0]))
    if (spread[0] < 180 or spread[1] < 120 or not 0.98 <= scale <= 1.02
            or abs(angle) > 2 or np.linalg.norm(transform[:, 2]) > 80):
        return None
    polygon = np.rint(cv2.transform(np.float32([reference_zone.polygon]), transform)[0]).astype(np.int32)
    interior = np.zeros((720, 1280), np.uint8)
    cv2.fillConvexPoly(interior, polygon, 255)
    interior[(~gray) | (allowed == 0)] = 0
    # Boats, troops, waves and UI holes all reduce clearance. Never click through them.
    clearance = cv2.distanceTransform(interior, cv2.DIST_L2, 5)
    if clearance.max() < 12:
        return None
    point = None
    if preferred_point is not None:
        x, y = preferred_point
        if 0 <= x < 1280 and 0 <= y < 720 and clearance[y, x] >= 12:
            point = (int(x), int(y))
    if point is None:
        y, x = np.unravel_index(np.argmax(clearance), clearance.shape)
        point = (int(x), int(y))
    return LandingZone(point, tuple(tuple(int(v) for v in p) for p in polygon),
                       float(min(reference_zone.score, 0.90)))
