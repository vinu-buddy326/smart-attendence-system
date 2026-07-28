from deep_sort_realtime.deepsort_tracker import DeepSort

class ObjectTracker:
    def __init__(self, max_age=30, n_init=3, nms_max_overlap=0.7):
        self.tracker = DeepSort(max_age=max_age, n_init=n_init, nms_max_overlap=nms_max_overlap)

    def update_tracker(self, detections, frame):
        # Detections: list of ([x, y, w, h], confidence, 'class')
        tracks = self.tracker.update_tracks(detections, frame=frame)
        active_tracks = []
        for track in tracks:
            if not track.is_confirmed() or track.time_since_update > 1:
                continue
            track_id = track.track_id
            ltrb = track.to_ltrb() # [left, top, right, bottom]
            active_tracks.append((track_id, ltrb))
        return active_tracks
