# 初始数据结构
SQLAlchemy metadata创建schema；后续版本应新增真实迁移。唯一约束为sample_batches.code、sample_units(batch_id,code)、margin_targets(batch_id,dimension,category)、weight_reviews.run_id、users.email。不可用create_all做列变更。

## 重抽样分析（新增表，非列变更）
`bootstrap_analyses` 由同一metadata创建，记录 run_id、replicates、seed、status、result(JSON)、error、created_by、created_at。不改动 `weight_runs` 任何列；旧库首次启动时create_all会补建该表。
