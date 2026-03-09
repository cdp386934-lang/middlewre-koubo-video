# 背景音乐数组功能

## 功能概述

支持在视频草稿中添加多个背景音乐片段，每个片段可以独立设置：
- 播放时间段（开始/结束时间）
- 音量大小
- 音频文件路径

## 配置方式

在 `config/config.yaml` 中添加 `bgm` 配置节：

```yaml
bgm:
  enabled: true
  default_volume: 0.3
  segments:
    - path: "assets/bgm/intro.mp3"
      start: 0.0
      end: 10.0
      volume: 0.5
    - path: "assets/bgm/main.mp3"
      start: 10.0
      end: 60.0
    - path: "assets/bgm/outro.mp3"
      start: 60.0
      end: null  # 播放到音频文件结束
```

## 参数说明

### BGM 配置

- `enabled`: 是否启用 BGM 功能（true/false）
- `default_volume`: 默认音量（0.0-2.0，默认 0.3）
- `segments`: BGM 片段列表

### 片段配置

- `path`: 音频文件路径（相对或绝对路径）
- `start`: 开始时间（秒）
- `end`: 结束时间（秒，null 表示播放到音频结束）
- `volume`: 音量（0.0-2.0，可选，不设置则使用 default_volume）

## 使用示例

### 示例 1: 单个 BGM

```yaml
bgm:
  enabled: true
  default_volume: 0.3
  segments:
    - path: "assets/bgm/background.mp3"
      start: 0.0
      end: null  # 播放完整音频
```

### 示例 2: 多段 BGM

```yaml
bgm:
  enabled: true
  default_volume: 0.3
  segments:
    - path: "assets/bgm/intro.mp3"
      start: 0.0
      end: 5.0
      volume: 0.5
    - path: "assets/bgm/main.mp3"
      start: 5.0
      end: 55.0
      volume: 0.3
    - path: "assets/bgm/outro.mp3"
      start: 55.0
      end: 60.0
      volume: 0.4
```

### 示例 3: 禁用 BGM

```yaml
bgm:
  enabled: false  # 快速禁用
  default_volume: 0.3
  segments: []
```

## 技术实现

### 新增文件

- `src/models/bgm.py`: BGM 数据模型（BGMSegment, BGMData）

### 修改文件

- `src/modules/bgm_manager.py`: 完全重写，支持数组配置
- `src/services/capcut_service.py`: 新增 `add_bgm_segments()` 方法
- `src/modules/draft_generator.py`: 更新 `generate()` 方法签名
- `src/pipeline.py`: 更新 BGM 处理流程
- `config/config.yaml`: 添加 BGM 配置节

### 向后兼容

- 保留了 `add_audios()` 方法
- `generate()` 方法的旧参数 `bgm_path` 仍然有效
- 如果没有 BGM 配置，行为与之前完全相同

## 验证方法

1. 准备测试音频文件
2. 在 `config.yaml` 中配置 BGM
3. 运行 `koubo-video.py` 处理视频
4. 检查日志输出确认 BGM 片段加载
5. 在剪映中打开草稿验证音频轨道

## 注意事项

- 音频文件必须存在，否则该片段会被跳过
- `end` 时间必须大于 `start` 时间
- 音量范围为 0.0-2.0
- 相对路径相对于项目根目录（input 目录的父目录）
- 多个片段可以重叠播放
- 淡入淡出功能暂未实现

## 常见问题

### Q: 如何快速禁用 BGM？
A: 设置 `enabled: false`

### Q: 如何让音乐播放到结束？
A: 设置 `end: null`

### Q: 音量范围是多少？
A: 0.0-2.0，其中 0.0=静音，1.0=原始音量，2.0=两倍音量

### Q: 支持哪些音频格式？
A: 支持剪映支持的所有音频格式（mp3, wav, m4a 等）

### Q: 片段可以重叠吗？
A: 可以，多个片段可以在同一时间段播放
