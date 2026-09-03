# 参与 BeatSync Studio 开发

感谢你愿意参与。这个项目优先保持安装简单、模块边界清晰，并通过小规模真实视频逐步验证准确率。

## 开发环境

Windows：

```powershell
.\scripts\setup.ps1
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

macOS / Linux：

```bash
bash scripts/setup.sh
./.venv/bin/python -m unittest discover -s tests -v
```

提交代码前请运行：

```bash
python -m unittest discover -s tests -v
ruff check src tests
```

## 建议的改动流程

1. 先创建 Issue，说明问题、预期行为和建议范围。
2. 每个 Pull Request 尽量只解决一个问题。
3. 行为变化应包含测试，并同步更新 README 或命令帮助。
4. 不要提交模型文件、下载的视频、人物照片、输出片段或其他大文件。
5. 不要加入默认读取浏览器 Cookie、绕过访问控制或规避平台限制的行为。

## Bug 报告

请提供操作系统和 Python 版本、`beatsync doctor` 输出、执行命令、错误信息，以及是否能在较小且可合法分享的素材上复现。

请勿公开上传私人照片、未授权影视素材、Cookie、访问令牌或其他敏感信息。

## 项目边界

V1 聚焦“目标人物 → 时间段 → 高清片段”。GUI、语义搜索、参考剪辑分析和自动特效属于后续阶段，不应让当前核心流程变得难以安装或调试。

