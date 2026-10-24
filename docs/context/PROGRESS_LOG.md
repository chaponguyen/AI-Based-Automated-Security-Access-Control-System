# TIẾN ĐỘ (mỗi Agent thêm một mục sau mỗi lần làm việc)

(Chưa có mục nào)
- 2026-10-24 19:32 [B2] CP-01 (backend/ai/detector.py; backend/ai/config.py): detector.py: them get_app() nap FaceAnalysis('buffalo_sc', CPUExecutionProvider) mot lan (thread-safe), prepare(ctx_id=-1, det_size=(640,640)); detect_faces() goi app.det_model.detect(max_num=0, metric='default'), tra list dict(bbox 4 so, kps 5x2, score), bo score < 0.5, sap theo dien tich giam dan. config.py: DET_SIZE, DET_SCORE_MIN va cac nguong cho CP-04..06.
- 2026-10-24 20:12 [B2] CP-02 (backend/ai/aligner.py; backend/ai/config.py): aligner.py: crop_face() dung insightface.utils.face_align.norm_crop voi 5 landmark, tra anh 112x112 BGR uint8; them _landmarks_5x2() chuan hoa va kiem tra kps (None/sai hinh dang/NaN/hai mat trung nhau -> ValueError), kiem tra ca anh None/rong/xam. config.py: them CROP_SIZE = 112.
