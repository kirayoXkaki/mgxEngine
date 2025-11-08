# 如何获取 SUPABASE_DB_URL

## 步骤 1: 创建或登录 Supabase 项目

1. 访问 [https://app.supabase.com](https://app.supabase.com)
2. 登录你的账户（如果没有账户，先注册）
3. 如果还没有项目，点击 **"New Project"** 创建新项目
4. 如果已有项目，直接选择项目进入

## 步骤 2: 获取数据库连接字符串

### 方式 A: 从 Database Settings 获取（推荐）

1. 在项目控制台中，点击左侧菜单的 **Settings**（设置）
2. 选择 **Database**（数据库）
3. 向下滚动到 **Connection string**（连接字符串）部分
4. 你会看到几个标签页：
   - **URI** - 这是你需要的格式
   - **JDBC** - Java 使用
   - **Golang** - Go 语言使用
   - **Python** - Python 使用（但我们需要 URI 格式）

5. 点击 **URI** 标签页
6. 你会看到类似这样的连接字符串：
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres
   ```

### 方式 B: 从 Connection Pooling 获取（如果使用连接池）

1. 在 **Settings → Database** 页面
2. 找到 **Connection Pooling** 部分
3. 选择 **Session mode** 或 **Transaction mode**
4. 复制连接字符串（格式类似，但端口可能是 6543）

## 步骤 3: 处理密码中的特殊字符

如果你的数据库密码包含特殊字符（如 `@`, `#`, `%`, `&` 等），需要进行 URL 编码：

### 常见特殊字符编码表：

| 字符 | URL 编码 |
|------|----------|
| `@`  | `%40`    |
| `#`  | `%23`    |
| `%`  | `%25`    |
| `&`  | `%26`    |
| `+`  | `%2B`    |
| `=`  | `%3D`    |
| `?`  | `%3F`    |
| `/`  | `%2F`    |
| `:`  | `%3A`    |
| ` ` (空格) | `%20` |

### 示例：

如果你的密码是 `Qq@1974248087`：
- 原始密码：`Qq@1974248087`
- 编码后：`Qq%401974248087`（`@` 变成 `%40`）

### 自动编码方法：

你可以使用 Python 来编码密码：

```python
from urllib.parse import quote

password = "Qq@1974248087"
encoded = quote(password, safe='')
print(encoded)  # 输出: Qq%401974248087
```

## 步骤 4: 构建完整的 SUPABASE_DB_URL

### 格式：

```
postgresql+asyncpg://postgres:ENCODED_PASSWORD@db.PROJECT_ID.supabase.co:5432/postgres
```

### 组成部分：

1. **协议**: `postgresql+asyncpg://`（使用 asyncpg 驱动，推荐）
   - 或者 `postgresql://`（使用 psycopg 驱动）

2. **用户名**: `postgres`（Supabase 默认用户名）

3. **密码**: `ENCODED_PASSWORD`（URL 编码后的密码）

4. **主机名**: `db.PROJECT_ID.supabase.co`
   - `PROJECT_ID` 是你的项目引用 ID
   - 注意：必须是 `db.` 开头，不是 `https://`

5. **端口**: `5432`（PostgreSQL 默认端口）

6. **数据库名**: `postgres`（Supabase 默认数据库）

### 完整示例：

假设：
- 项目 ID: `abcdefghijklmnop`
- 密码: `MyP@ssw0rd#123`

构建过程：
1. 编码密码：`MyP@ssw0rd#123` → `MyP%40ssw0rd%23123`
2. 完整 URL：
   ```
   postgresql+asyncpg://postgres:MyP%40ssw0rd%23123@db.abcdefghijklmnop.supabase.co:5432/postgres
   ```

## 步骤 5: 更新 .env 文件

在 `backend/.env` 文件中添加：

```bash
SUPABASE_DB_URL=postgresql+asyncpg://postgres:YOUR_ENCODED_PASSWORD@db.YOUR_PROJECT_ID.supabase.co:5432/postgres
```

**重要提示：**
- 替换 `YOUR_ENCODED_PASSWORD` 为编码后的密码
- 替换 `YOUR_PROJECT_ID` 为你的项目 ID
- 确保密码中的特殊字符已正确编码

## 步骤 6: 测试连接

运行测试脚本验证连接：

```bash
cd backend
python3 scripts/test_supabase_connection.py
```

## 常见问题

### Q: 如何找到项目 ID？

A: 项目 ID 在以下位置可以找到：
- Settings → General → Reference ID
- Settings → Database → Connection string 中的主机名部分
- 项目 URL 中：`https://app.supabase.com/project/YOUR_PROJECT_ID`

### Q: 密码在哪里？

A: 密码是在创建 Supabase 项目时设置的数据库密码。如果你忘记了：
1. 无法直接查看密码
2. 可以在 Settings → Database → Database password 中重置密码
3. 重置后需要更新连接字符串

### Q: 应该使用哪个驱动？

A: 
- **asyncpg**（推荐）：异步性能更好，适合 FastAPI
  - URL 格式：`postgresql+asyncpg://...`
- **psycopg**：同步驱动，更稳定
  - URL 格式：`postgresql://...` 或 `postgresql+psycopg://...`

### Q: 连接失败怎么办？

A: 检查以下几点：
1. 项目是否处于 Active 状态（不是 Paused）
2. 主机名是否正确（必须是 `db.PROJECT_ID.supabase.co`）
3. 密码是否正确编码
4. 网络连接是否正常
5. IP 地址是否被 Supabase 防火墙阻止（默认允许所有 IP）

### Q: 如何重置数据库密码？

A:
1. 进入 Settings → Database
2. 找到 Database password 部分
3. 点击 "Reset database password"
4. 设置新密码
5. 更新 `.env` 文件中的连接字符串

## 快速检查清单

- [ ] 已登录 Supabase 控制台
- [ ] 已选择正确的项目
- [ ] 已从 Settings → Database 复制连接字符串
- [ ] 已处理密码中的特殊字符（URL 编码）
- [ ] 已确认主机名格式为 `db.PROJECT_ID.supabase.co`
- [ ] 已更新 `.env` 文件
- [ ] 已运行测试脚本验证连接

## 示例：完整的获取流程

1. **打开 Supabase 控制台**
   ```
   https://app.supabase.com
   ```

2. **进入项目 → Settings → Database**

3. **找到 Connection string → URI 标签页**

4. **复制连接字符串**（示例）：
   ```
   postgresql://postgres:MyP@ssw0rd@db.abcdefghijklmnop.supabase.co:5432/postgres
   ```

5. **如果密码包含特殊字符，手动编码**：
   - 原始：`MyP@ssw0rd`
   - 编码：`MyP%40ssw0rd`

6. **构建最终 URL**：
   ```
   postgresql+asyncpg://postgres:MyP%40ssw0rd@db.abcdefghijklmnop.supabase.co:5432/postgres
   ```

7. **添加到 .env 文件**：
   ```bash
   SUPABASE_DB_URL=postgresql+asyncpg://postgres:MyP%40ssw0rd@db.abcdefghijklmnop.supabase.co:5432/postgres
   ```

8. **测试连接**：
   ```bash
   python3 scripts/test_supabase_connection.py
   ```

