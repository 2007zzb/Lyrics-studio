#!/usr/bin/env bash
# 打包 Android APK
# 用法： bash build_android.sh
# 环境： Linux / macOS（Windows 请用 Git Bash 或 WSL）
# 首次运行会自动下载 Flutter 与 Android SDK，需要 20~40 分钟，请耐心等待。

set -e

PROJECT_NAME="歌词修改工作台"   # 仅用于显示提示
ORG="com.zxb"
# 注意：传给 flet build 的名字必须用英文。
# Flet 0.25 已知 bug：项目名含中文会导致打包产物启动失败。

# 用 python -m 的方式调用，不依赖 PATH 里有没有 flet 命令。
# 直接敲 flet 经常报「command not found」，
# 因为 pip 装的脚本目录（如 ~/.local/bin）不一定在 PATH 里。
run_flet() {
  python -c "import sys; from flet.cli import main; sys.argv = ['flet'] + sys.argv[1:]; main()" "$@"
}

echo "==> 检查 flet 打包依赖"
python -m pip install "flet[all]==0.25.2" --upgrade

echo "==> 开始构建 APK（第一次会比较慢）"
# 注意：flet build 没有 --artifact 这个参数，加了会报错退出（码 2）。
# 产物名由 --project 决定，生成的是 build/apk/<project>.apk
run_flet build apk \
  --project lyrics_studio \
  --product LyricStudio \
  --org "$ORG"

echo
echo "==> 完成！产物在 build/apk/ 目录下"
ls -lh build/apk/*.apk 2>/dev/null || echo "（没找到 apk，请查看上面的报错信息）"
