# Pexels素材获取功能

## 功能概述

该功能自动从Pexels获取与视频内容相关的素材(视频和图片),并将其添加到剪映草稿中。

## 配置

### 1. 获取Pexels API Key

访问 [Pexels API](https://www.pexels.com/api/) 注册并获取免费的API key。

### 2. 配置环境变量

在`.env`文件中添加:

```bash
PEXELS_API_KEY=your_pexels_api_key_here
```

### 3. 配置参数

在`config/config.yaml`中可以调整以下参数:

```yaml
pexels:
  enabled: true              # 是否启用素材功能
  max_keywords: 5            # 最多为几个关键词搜索素材
  per_keyword: 5             # 每个关键词获取几个素材
  orientation: "landscape"   # 素材方向: landscape/portrait/square
  video_quality: "hd"        # 视频质量: hd/sd
  photo_size: "large"        # 图片尺寸: original/large/medium/small
  rate_limit_delay: 0.5      # API请求间隔(秒)
```

## 工作流程

1. **关键词提取**: 从DeepSeek AI提取的关键词中选择重要性最高的5个
2. **素材搜索**: 为每个关键词从Pexels搜索5个视频和5个图片
3. **素材映射**: 将素材映射到对应的字幕时间段
4. **添加到草稿**: 自动将素材添加到剪映草稿的track 2
5. **元数据保存**: 保存素材信息到`output/materials/metadata.json`

## 输出

- `output/materials/metadata.json`: 包含所有获取的素材信息

## 禁用功能

如果不需要素材功能,可以:

1. 在`config.yaml`中设置`pexels.enabled: false`
2. 或者不配置`PEXELS_API_KEY`环境变量

系统会自动跳过素材获取步骤。

## API限制

Pexels免费API限制:
- 每小时200次请求
- 每月20,000次请求

建议合理设置`max_keywords`和`per_keyword`参数以避免超出限制。
