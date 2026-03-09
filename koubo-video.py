# 输入：一个未进行加工的视频；

# 输出：
#     - 视频转音频提取
#未加工视频 (video.mp4)
    # ↓
# [步骤1] 视频转音频
#     ↓
# video.wav (提取的音频)
#     ↓
# [步骤2] 音频转文字（ASR）
#     ↓
# video.json (生成字幕)
#     ↓
# [步骤3] 去气口处理
#     ↓
# video.json (标记气口: removed=1)
# video_no_breath.wav (去气口音频)
# video_no_breath.mp4 (去气口视频)
#     ↓
# [步骤4] 生成关键字并贴入字幕
#     ↓
#     [4.1] DeepSeek AI分析字幕
#     [4.2] 提取核心关键词
#     [4.3] 贴入字幕（加引号）
#     [4.4] 保存到JSON
#     ↓
# video.json (包含关键词的字幕)
# modules/output/keywords.json (关键词列表)
#     ↓
# [步骤5] 素材获取与插入（可选）
#     ↓
# [步骤6] 添加背景音乐
#     ↓
# [步骤7] 应用视频信息
#     ↓
# [步骤8] 生成剪映草稿
#     ↓
# JianyingPro/草稿/ (剪映草稿)