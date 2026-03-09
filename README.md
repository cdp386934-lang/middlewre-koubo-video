# middleware-koubo-video

视频处理中间件，将未加工的视频自动处理并生成剪映草稿。

## 功能特性

- ✅ 视频转音频（FFmpeg）
- ✅ 音频转文字（Whisper ASR）
- ✅ 关键词提取（DeepSeek AI）
- ✅ 字幕生成（带关键词高亮）
- ✅ 剪映草稿生成（CapCut-mate API）
- ✅ 去气口处理（压缩口播停顿）
- ✅ LLM 自动标题 + 作者身份文案轨道
- 🚧 素材管理（预留接口）
- 🚧 背景音乐（预留接口）

## 工作流程

```
输入视频 (未加工.mp4)
    ↓
[步骤1] FFmpeg 提取音频
    ↓
音频文件 (video.wav)
    ↓
[步骤2] Whisper ASR
    ↓
字幕 JSON (video.json)
    ↓
[步骤3] 去气口检测与时间轴压缩
    ↓
[步骤4] DeepSeek AI 分析 + auto_jianying 风格关键词标注
    ↓
关键词 JSON + 更新字幕 JSON（含 `keyword` / `text_grade` / `video_grade` / `removed`）
    ↓
[步骤6-7] 背景音乐 + 视频信息
    ↓
[步骤8] CapCut-mate API
    ↓
剪映草稿 (可在剪映中打开)
```

## 安装

### 1. 系统依赖

确保已安装 FFmpeg：

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows
# 下载并安装 FFmpeg: https://ffmpeg.org/download.html
```

### 2. 创建虚拟环境并安装 Python 依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

如果在安装 `openai-whisper` 时遇到 `No module named 'pkg_resources'`，可执行：

```bash
pip install "setuptools<81"
pip install --no-build-isolation openai-whisper==20231117
pip install -r requirements.txt
```

### 3. 配置

复制配置模板：

```bash
cp config/config.yaml config/config.yaml
cp .env.example .env
```

编辑 `.env` 文件，添加 DeepSeek API Key：

```
DEEPSEEK_API_KEY=your_api_key_here
```

### 4. CapCut-mate 服务

确保 capcut-mate 服务已启动（默认端口 30000）。

## 使用

将视频文件放入 `input/` 目录，然后运行：

```bash
python src/main.py
```

处理完成后，可以在剪映专业版中打开生成的草稿。

## 项目结构

```
middleware-koubo-video/
├── config/
│   └── config.yaml              # 配置文件
├── src/
│   ├── main.py                  # 主入口
│   ├── pipeline.py              # 工作流编排器
│   ├── modules/                 # 处理模块
│   │   ├── video_to_audio.py   # 视频转音频
│   │   ├── asr.py               # 音频转文字
│   │   ├── breath_removal.py   # 去气口处理
│   │   ├── keyword_extractor.py # 关键词提取
│   │   ├── material_manager.py  # 素材管理
│   │   ├── bgm_manager.py       # 背景音乐
│   │   ├── video_info.py        # 视频信息
│   │   └── draft_generator.py   # 剪映草稿生成
│   ├── services/                # 外部服务
│   │   ├── whisper_service.py   # Whisper ASR
│   │   ├── deepseek_service.py  # DeepSeek AI
│   │   └── capcut_service.py    # CapCut-mate API
│   ├── models/                  # 数据模型
│   │   ├── subtitle.py
│   │   ├── keyword.py
│   │   └── draft.py
│   └── utils/                   # 工具函数
│       ├── logger.py
│       └── file_handler.py
├── input/                       # 输入视频
├── output/                      # 输出文件
│   ├── audio/
│   ├── subtitles/
│   ├── keywords/
│   └── drafts/
└── logs/                        # 日志文件
```

## 配置说明

主要配置项（`config/config.yaml`）：

- `whisper.model_size`: Whisper 模型大小（tiny, base, small, medium, large）
- `whisper.device`: 运行设备（cpu 或 cuda）
- `deepseek.api_key`: DeepSeek API Key
- `capcut.api_url`: CapCut-mate API 地址
- `subtitle.font_size`: 字幕字体大小
- `subtitle.keyword_color`: 关键词高亮颜色

## 常见问题

### 1. Whisper 模型下载慢

首次运行会自动下载 Whisper 模型（约 140MB for base model）。如果下载慢，可以手动下载后放到缓存目录。

### 2. GPU 加速

如果有 NVIDIA GPU，可以在配置中设置 `whisper.device: cuda` 以加速 ASR 处理。

### 3. CapCut-mate 连接失败

确保 capcut-mate 服务已启动，并检查配置中的 API URL 是否正确。

## 许可证

MIT
