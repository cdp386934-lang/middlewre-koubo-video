# CapCut-mate API 使用指南

## 问题：为什么访问草稿 URL 显示"无效路由"或"无效的草稿URL"？

### 原因

CapCut-mate 返回的 URL（如 `https://capcut-mate.jcaigc.cn/openapi/capcut-mate/v1/get_draft?draft_id=xxx`）**不是用于浏览器直接访问的**，而是：

1. **API 内部引用地址** - 只能通过 API 调用访问
2. **草稿标识符** - 用于在 API 调用中引用草稿

### 正确的使用方式

#### 1. 通过程序自动处理（推荐）

运行我们的程序，它会自动完成所有步骤：

```bash
python3 src/main.py
```

程序会：
- ✅ 创建草稿
- ✅ 添加视频片段
- ✅ 添加字幕
- ✅ 自动保存草稿

#### 2. 在剪映中查看草稿

草稿生成后，有两种方式查看：

**方式 A：直接在剪映中打开**
1. 打开剪映专业版
2. 在草稿列表中查找名为"未加工"的草稿
3. 双击打开编辑

**方式 B：通过 CapCut-mate 查看草稿文件**

草稿文件保存在 CapCut-mate 的输出目录中。你可以：

```bash
# 查看草稿信息
python3 draft_manager.py <draft_id>

# 例如：
python3 draft_manager.py 202603091844518f128738
```

#### 3. 手动调用 API（高级用户）

如果需要手动调用 API，必须使用正确的方式：

```bash
# ❌ 错误：在浏览器中访问
# https://capcut-mate.jcaigc.cn/openapi/capcut-mate/v1/get_draft?draft_id=xxx

# ✅ 正确：通过本地 API 访问
curl "http://localhost:30000/openapi/capcut-mate/v1/get_draft?draft_id=xxx"

# ✅ 正确：保存草稿
curl -X POST http://localhost:30000/openapi/capcut-mate/v1/save_draft \
  -H "Content-Type: application/json" \
  -d '{"draft_url": "https://capcut-mate.jcaigc.cn/openapi/capcut-mate/v1/get_draft?draft_id=xxx"}'
```

### 常见错误

#### 错误 1：`{"code":2001,"message":"无效的草稿URL"}`

**原因：**
- 传递的 `draft_url` 格式不正确
- 或者 draft_id 不存在

**解决：**
- 确保使用完整的 URL：`https://capcut-mate.jcaigc.cn/openapi/capcut-mate/v1/get_draft?draft_id=xxx`
- 确保 draft_id 是有效的

#### 错误 2：浏览器访问显示"无效路由"

**原因：**
- 那个 URL 不是给浏览器访问的

**解决：**
- 不要在浏览器中访问
- 使用本地 API：`http://localhost:30000/openapi/capcut-mate/v1/get_draft?draft_id=xxx`

### 验证草稿是否生成成功

使用我们提供的工具：

```bash
# 查看最近生成的草稿
python3 draft_manager.py <draft_id>

# 或者查看输出目录
ls -la output/drafts/
cat output/drafts/*_metadata.json
```

### 草稿文件位置

草稿文件可能保存在以下位置之一：

1. **CapCut-mate 输出目录**（取决于 CapCut-mate 配置）
2. **剪映草稿目录**：
   ```
   ~/Library/Containers/com.lemon.lvpro/Data/Movies/JianyingPro/User Data/Projects/com.lveditor.draft/
   ```

### 总结

- ✅ 使用 `python3 src/main.py` 自动处理
- ✅ 在剪映专业版中查看草稿
- ✅ 使用 `draft_manager.py` 查看草稿信息
- ❌ 不要在浏览器中访问草稿 URL
- ❌ 不要手动调用 API（除非你知道自己在做什么）

### 需要帮助？

如果遇到问题：

1. 检查 CapCut-mate 服务是否运行：`curl http://localhost:30000/`
2. 查看程序日志：`tail -f logs/app.log`
3. 运行测试脚本：`python3 test_capcut_api.py`
