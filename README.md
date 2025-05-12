# <center>EngineeringCloudScript 使用文档</center>

工学云自动化脚本，支持自动签到、提交周报/月报，支持多用户管理。

## 1. 环境要求

### 基础环境

- **Python**: 3.10 或更高版本
- **包管理器**:
    - 推荐使用 `uv` 0.6.16+
    - 也可使用 `pip` 或其他兼容的 Python 包管理器

## 2. 快速开始

### 2.1 获取代码

```bash
git clone https://github.com/Huee1213/EngineeringCloudScript.git
cd EngineeringCloudScript
```

### 2.2 安装依赖

#### 使用 uv 包管理器（推荐）

```bash
uv sync
```

#### 使用 pip 包管理器

```bash
pip install -r requirements-prod.txt
```

### 2.3 运行模式

#### 定时任务模式（默认）

```bash
python main.py
```

#### 单次执行模式

```bash
python main.py --single
```

## 3. 配置说明

### 3.1 .env 配置文件

根据 `.env.example` 创建 `.env` 文件并配置以下参数：

#### AI 服务配置

```ini
# AI 服务提供商的基础 API 地址
# 示例: OpenAI 官方 API
AI_BASE_URL = "https://api.openai.com/v1"

# 选择使用的 AI 模型
# 可选: "gpt-3.5-turbo", "gpt-4" 等
AI_MODEL = "gpt-3.5-turbo"

# AI 服务的 API 密钥 (敏感信息，请妥善保管)
AI_API_KEY = "sk-your-api-key-here"
```

#### 邮件通知配置

```ini
# 邮件主题 (默认无需修改)
SUBJECT = "工学云自动化脚本提醒"

# 发件邮箱配置
SENDER_EMAIL = "your-email@example.com"
SENDER_PASSWORD = "your-email-password"  # 或应用专用密码

# SMTP 服务器配置
# 常见服务商:
#   Gmail: smtp.gmail.com
#   QQ邮箱: smtp.qq.com 
#   163邮箱: smtp.163.com
SMTP_SERVER = "smtp.example.com"
SMTP_PORT = "465"  # 通常为 465(SSL) 或 587(TLS)
```

### 3.2 用户配置文件 (users.json)

#### 3.2.1 配置文件说明

1. 复制`data`目录下的`users.example.json` 为 `users.json`
2. 支持配置多个用户账号
3. 每个用户包含以下配置项：
    - 基本信息：用户名、邮箱、工学云账号密码
    - 工作设置：岗位信息
    - 时间设置：签到、周报、月报时间
    - 地址设置：签到定位信息

#### 3.2.2 配置示例

```json
{
	"users": [
		{
			"username": "张三",
			"email": "zhangsan@example.com",
			"phone": "13800138000",
			"password": "your_password",
			"configInfo": {
				"jobSetting": {
					"post": "软件开发工程师"
				},
				"timeSetting": {
					"signInTime": {
						"start": "09",
						"end": "18"
					},
					"weeklyReportTime": {
						"week": "5",
						"time": "17"
					},
					"monthlyReportTime": {
						"day": "25",
						"time": "17"
					}
				},
				"addressSetting": {
					"country": "中国",
					"province": "北京市",
					"city": "北京市",
					"area": "海淀区",
					"address": "中国 · 北京市 · 北京市 · 海淀区 · 中关村软件园1号楼",
					"longitude": "116.301",
					"latitude": "39.987"
				}
			}
		},
		{
			"username": "李四",
			"email": "lisi@example.com",
			"phone": "13900139000",
			"password": "your_password",
			"configInfo": {
				"jobSetting": {
					"post": "产品经理"
				},
				"timeSetting": {
					"signInTime": {
						"start": "09",
						"end": "18"
					},
					"weeklyReportTime": {
						"week": "5",
						"time": "18"
					},
					"monthlyReportTime": {
						"day": "28",
						"time": "18"
					}
				},
				"addressSetting": {
					"country": "中国",
					"province": "上海市",
					"city": "上海市",
					"area": "浦东新区",
					"address": "中国 · 上海市 · 上海市 · 浦东新区 · 张江高科技园区",
					"longitude": "121.593",
					"latitude": "31.204"
				}
			}
		}
	]
}
```

#### 3.2.3 配置项详解

1. **基础信息**:
    - `username`: 用户昵称（仅用于标识）
    - `email`: 接收通知的邮箱
    - `phone`: 工学云登录手机号
    - `password`: 工学云登录密码

2. **工作设置**:
    - `post`: 工作岗位名称（将用于报告内容生成）

3. **时间设置（以下任意选项配置为空时，则在定时任务中不会执行该任务）**:
    - `signInTime`: 每日签到时间范围
        - `start`: 上班时间（格式: HH）
        - `end`: 下班时间（格式: HH）
    - `weeklyReportTime`: 周报提交时间
        - `week`: 星期几（1-7，1=周一）
        - `time`: 提交时间（格式: HH）
    - `monthlyReportTime`: 月报提交时间
        - `day`: 每月几号（1-28）
        - `time`: 提交时间（格式: HH）

4. **地址设置**:
    - 所有地址字段为签到定位使用
    - `longitude`/`latitude`: 经纬度坐标（十进制格式）

#### 3.2.4 注意事项

1. 时间格式必须严格遵循 `HH` 24小时制
2. 经纬度可通过地图应用获取（如百度地图、高德地图）
3. 添加新用户时，请确保JSON格式正确（可借助JSON验证工具检查）
4. 建议使用代码编辑器（如VSCode）编辑，避免格式错误

## 4. 安全提示

1. **敏感信息保护**:
    - 切勿将 `.env` 和 `users.json` 文件提交到公开版本控制系统
    - 建议将 `.env` 和 `users.json` 添加到 `.gitignore`

2. **API 密钥管理**:
    - 定期轮换 API 密钥
    - 为生产环境使用最小权限原则

3. **邮件账户安全**:
    - 建议使用应用专用密码而非账户主密码
    - 启用邮箱的二次验证功能

## 6. 问题排查

如有疑问提交 issue 到项目仓库。

---

> 最后更新: 2025-05-12  
> 项目维护者: Huee1213  
> 许可证: MIT