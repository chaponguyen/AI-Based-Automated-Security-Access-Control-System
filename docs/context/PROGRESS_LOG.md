# TIẾN ĐỘ (mỗi Agent thêm một mục sau mỗi lần làm việc)

(Chưa có mục nào)
- 2026-10-24 19:32 [B2] CP-01 (backend/ai/detector.py; backend/ai/config.py): detector.py: them get_app() nap FaceAnalysis('buffalo_sc', CPUExecutionProvider) mot lan (thread-safe), prepare(ctx_id=-1, det_size=(640,640)); detect_faces() goi app.det_model.detect(max_num=0, metric='default'), tra list dict(bbox 4 so, kps 5x2, score), bo score < 0.5, sap theo dien tich giam dan. config.py: DET_SIZE, DET_SCORE_MIN va cac nguong cho CP-04..06.
