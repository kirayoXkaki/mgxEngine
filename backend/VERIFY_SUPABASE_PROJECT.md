# 验证 Supabase 项目状态

## 问题诊断

DNS 解析失败说明主机名 `db.gvutqlngvhvyeerselwu.supabase.co` 无法解析。

## 验证步骤

### 1. 检查项目状态

1. 登录 [Supabase 控制台](https://app.supabase.com)
2. 找到项目 `gvutqlngvhvyeerselwu`（或对应的项目）
3. 检查项目状态：
   - ✅ **Active** - 项目正常运行
   - ⏸️ **Paused** - 项目已暂停（需要恢复）
   - ❌ **Deleted** - 项目已删除

### 2. 获取正确的项目引用 ID

**方法 A: 从项目设置**
1. 进入项目 → **Settings** → **General**
2. 查看 **Reference ID**（不是 Project ID）
3. 格式应该是类似：`abcdefghijklmnop`（24 个字符）

**方法 B: 从数据库连接字符串**
1. 进入项目 → **Settings** → **Database**
2. 找到 **Connection string** → **URI** 标签页
3. 连接字符串中的主机名格式：`db.xxxxx.supabase.co`
4. `xxxxx` 就是你的项目引用 ID

### 3. 检查项目引用 ID 格式

Supabase 项目引用 ID 通常是：
- 24 个小写字母和数字的组合
- 例如：`abcdefghijklmnopqrstuvwx`

当前使用的 ID：`gvutqlngvhvyeerselwu`（22 个字符）

**可能的问题：**
- ID 长度不对（应该是 24 个字符）
- ID 中有大写字母（应该全部小写）
- ID 中有特殊字符（应该只有字母和数字）

### 4. 验证主机名格式

正确的 Supabase 数据库主机名格式：
```
db.PROJECT_REFERENCE_ID.supabase.co
```

**检查清单：**
- [ ] 以 `db.` 开头
- [ ] 项目引用 ID 全部小写
- [ ] 项目引用 ID 只有字母和数字
- [ ] 以 `.supabase.co` 结尾
- [ ] 没有 `https://` 前缀

### 5. 测试其他可能的格式

如果项目引用 ID 不正确，尝试：

1. **检查项目 URL**
   - 浏览器地址栏中的项目 URL
   - 格式：`https://app.supabase.com/project/PROJECT_REFERENCE_ID`
   - `PROJECT_REFERENCE_ID` 就是你要的 ID

2. **从 API 设置获取**
   - Settings → API
   - Project URL 中的 ID 部分

3. **从连接池获取**
   - Settings → Database → Connection Pooling
   - 连接字符串中的主机名

## 常见问题

### Q: 项目引用 ID 和 Project ID 有什么区别？

A:
- **Reference ID**: 用于数据库连接（24 个字符，小写字母和数字）
- **Project ID**: 用于 API 调用（UUID 格式）

数据库连接使用的是 **Reference ID**。

### Q: 如何确认项目引用 ID 是否正确？

A: 最简单的方法：
1. 从 Supabase 控制台直接复制连接字符串
2. 连接字符串中的主机名就是正确的格式
3. 提取其中的项目引用 ID

### Q: 项目已暂停怎么办？

A:
1. 进入项目设置
2. 找到 "Resume project" 或 "Restore project" 选项
3. 恢复项目后，数据库连接会自动恢复

### Q: 如何创建新项目？

A:
1. 登录 Supabase 控制台
2. 点击 "New Project"
3. 填写项目信息
4. 设置数据库密码
5. 等待项目创建完成（约 2 分钟）
6. 从 Settings → Database 获取连接字符串

## 下一步

1. **确认项目引用 ID**：从 Supabase 控制台直接复制连接字符串
2. **更新 .env 文件**：使用正确的连接字符串
3. **重新测试**：运行 `python3 scripts/test_supabase_connection.py`

## 快速验证命令

在 Supabase 控制台中：
1. Settings → Database → Connection string → URI
2. 复制完整的连接字符串
3. 检查主机名格式是否正确
4. 如果密码包含特殊字符，确保已正确编码

