# 快速开始指南

## 1. 安装依赖

```bash
pip install -r requirements.txt
```

**注意事项：**
- 首次运行 Whisper 会自动下载模型（约 140MB for base model）
- 如果需要 GPU 加速，确保安装了 CUDA 版本的 PyTorch
- FFmpeg 需要单独安装（macOS: `brew install ffmpeg`）

## 2. 配置环境

### 2.1 创建 .env 文件

```bash
cp .env.example .env
```

### 2.2 编辑 .env 文件，添加 DeepSeek API Key

```
DEEPSEEK_API_KEY=sk-your-api-key-here
```

获取 API Key: https://platform.deepseek.com/

### 2.3 配置 CapCut-mate

确保 capcut-mate 服务已启动：

```bash
# 启动 capcut-mate 服务（默认端口 30000）
# 具体启动方式请参考 capcut-mate 文档
```

如果 API 地址不同，修改 `config/config.yaml` 中的 `capcut.api_url`。

## 3. 准备输入视频

将要处理的视频文件放入 `input/` 目录：

```bash
cp /path/to/your/video.mp4 input/
```

## 4. 运行程序

```bash
python3 src/main.py
```

## 5. 查看结果

处理完成后，可以在以下位置找到输出文件：

- `output/audio/` - 提取的音频文件
- `output/subtitles/` - 字幕 JSON 文件
- `output/keywords/` - 关键词 JSON 文件
- `output/drafts/` - 草稿元数据
- `logs/` - 日志文件

打开剪映专业版，在草稿列表中可以看到新生成的草稿。

## 6. 验证安装

运行测试脚本验证项目结构：

```bash
python3 test_setup.py
```

## 常见问题

### Q1: ModuleNotFoundError

确保在项目根目录运行程序，或者使用：

```bash
cd /path/to/middleware-koubo-video
python3 src/main.py
```

### Q2: Whisper 模型下载慢

可以设置代理或手动下载模型文件。

### Q3: DeepSeek API 调用失败

检查：
1. API Key 是否正确
2. 网络连接是否正常
3. API 额度是否充足

### Q4: CapCut-mate 连接失败

检查：
1. capcut-mate 服务是否启动
2. API URL 是否正确
3. 端口是否被占用

## 配置优化

### 使用 GPU 加速

编辑 `config/config.yaml`：

```yaml
whisper:
  device: "cuda"  # 改为 cuda
```

### 更换 Whisper 模型

编辑 `config/config.yaml`：

```yaml
whisper:
  model_size: "small"  # 可选: tiny, base, small, medium, large
```

模型越大，准确度越高，但速度越慢。

### 调整关键词数量

编辑 `config/config.yaml`：

```yaml
keyword:
  max_count: 15  # 增加关键词数量
```

## 下一步

- 实现去气口处理功能
- 添加素材管理功能
- 添加背景音乐选择功能
- 支持批量处理多个视频
- 添加 Web UI 界面
