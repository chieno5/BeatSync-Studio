# BeatSync Studio

用一张人物照片，从本地视频文件夹或 Bilibili BV 视频中找到这个人出现的时间段，并自动导出高清片段。

> 项目处于 V1 开发期。当前先把人脸检索和素材提取做可靠，再逐步加入动作、场景、台词和参考剪辑分析。

## 5 分钟开始

需要 Python 3.10–3.12（推荐 3.12）。Python 3.13/3.14 暂未采用，因为部分 AI 依赖尚无稳定的预编译包。其余 Python 依赖和 FFmpeg 由安装脚本处理。

### Windows

```powershell
git clone https://github.com/chieno5/BeatSync-Studio.git
cd "BeatSync Studio"
.\scripts\setup.ps1
.\.venv\Scripts\beatsync.exe doctor
```

如果 PowerShell 禁止运行脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

### macOS / Linux

```bash
git clone https://github.com/chieno5/BeatSync-Studio.git
cd "BeatSync Studio"
bash scripts/setup.sh
./.venv/bin/beatsync doctor
```

安装成功后，无需手动激活虚拟环境，直接使用上述 `.venv` 中的 `beatsync` 即可。

## 查找本地视频中的人物

准备一张脸部清晰的照片，然后运行：

```powershell
.\.venv\Scripts\beatsync.exe scan-local `
  --reference .\person.jpg `
  --videos-dir D:\Videos `
  --output-dir .\output
```

macOS/Linux 将程序路径换成 `./.venv/bin/beatsync`，并使用 `\` 续行。

可以多次传入 `--reference`，正脸、侧脸各提供一张通常更稳定。

## 查找 Bilibili BV 视频中的人物

安装脚本默认包含在线模式所需的 yt-dlp：

```powershell
.\.venv\Scripts\beatsync.exe scan-bv `
  --reference .\person.jpg `
  --engine anime `
  --bv BV1xxxxxxxxx `
  --output-dir .\output
```

也可以多次传入 `--bv`。程序先下载不高于 480p 的代理视频进行初筛，确认命中后才下载高质量版本并导出片段。

如果 BV 是多 P 视频，请粘贴包含分 P 参数的完整链接，例如：

```powershell
--bv "https://www.bilibili.com/video/BV1xxxxxxxxx?p=109"
```

真人照片默认使用 `--engine real`。动漫或游戏角色使用 `--engine anime`；首次使用动漫模式会自动下载约 162 MB 的检测与角色识别模型，之后复用本地缓存。

请只下载和处理你有权使用的内容，并遵守网站服务条款及所在地法律。Bilibili 接口变化、登录要求或地区限制可能导致个别视频无法获取。

## 输出结果

```text
output/
  manifest.json         # 来源、时间段、相似度、错误和输出路径
  clips/
    video_0001_12.500-18.000.mp4
  work/                 # 在线模式临时文件
```

## 识别效果调整

先使用默认值测试。只有出现问题时再调整：

- 误认别人：提高 `--threshold`。真人模式可从 `0.55` 尝试，动漫模式可从 `0.90` 尝试。
- 漏掉目标人物：降低 `--threshold`。真人模式可从 `0.45` 尝试，动漫模式可从 `0.85` 尝试。
- 漏掉极短镜头：降低 `--sample-interval`，例如 `0.5`，但处理更慢。
- 只想查看时间段：加入 `--no-export`。

查看全部参数：

```powershell
.\.venv\Scripts\beatsync.exe scan-local --help
```

## 安装说明

首次运行人脸检索时会自动从 OpenCV 官方模型库下载 YuNet 和 SFace 模型，后续不会重复下载。当前使用兼容性更好的 OpenCV CPU 后端，无需配置 CUDA。贡献者可运行 `.\scripts\setup.ps1 -Dev` 额外安装测试和代码检查工具。

## 当前能力与限制

- 支持递归扫描常见视频格式。
- 支持多张参考照片和连续时间段合并。
- 从本地原视频或命中后的在线高清源导出片段。
- 当前按固定间隔抽帧，快速运动、严重侧脸、遮挡、小脸或低画质视频可能漏检。
- 尚未加入镜头边界二次精扫、人物索引数据库和断点续跑。
- YuNet/SFace 模型有独立许可和训练数据条件；用于商业产品前必须再次核实。

## 参与开发

请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。Bug 报告最好附上系统信息、`beatsync doctor` 输出以及可公开的最小复现素材；不要上传没有传播权限的视频或人物照片。

完整产品构想见 [PROJECT_IDEA.md](PROJECT_IDEA.md)。项目代码采用 [MIT License](LICENSE)；自动下载的第三方模型和在线媒体仍受其各自许可证、服务条款和内容权利约束。
