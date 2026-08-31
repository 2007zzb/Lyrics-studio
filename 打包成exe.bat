@echo off
chcp 936 >nul 2>&1
title 打包成 Windows 软件
cd /d "%~dp0"
setlocal enabledelayedexpansion

echo ============================================================
echo.
echo      歌词修改工作台   打包成 Windows 软件
echo.
echo ============================================================
echo.
echo   本脚本会自动选一条能走通的打包路线，你不用管细节：
echo.
echo   路线 A（首选）  检测到 Flutter SDK 时用
echo                  原生打包，体积小、启动快
echo.
echo   路线 B（兜底）  没装 Flutter 时自动用
echo                  基于 PyInstaller，不需要 Flutter SDK
echo                  产物稍大，功能完全一样
echo.
echo   两条路线都不需要你手动装 Flutter。
echo.
echo   另外：如果你把代码推到了 GitHub，
echo   打一个 v1.0.0 标签就能让云端自动打包，
echo   本机什么都不用装，那是最省事的办法。
echo.
echo ============================================================
echo.
pause

REM ============================================================
REM  第 1 步：找到 Python
REM ============================================================
set "PYCMD="
where python >nul 2>&1
if not errorlevel 1 set "PYCMD=python"
if not defined PYCMD (
    where py >nul 2>&1
    if not errorlevel 1 set "PYCMD=py -3"
)
if not defined PYCMD (
    echo.
    echo [错误] 没有检测到 Python。
    echo        请先安装 Python 3.10 或更高版本，
    echo        安装时记得勾选 Add Python to PATH。
    echo.
    pause
    exit /b 1
)

echo.
echo 使用的 Python 命令： %PYCMD%
%PYCMD% --version

REM 版本提醒：Flet 0.25 系列主要适配到 Python 3.12，
REM 3.13 / 3.14 上个别依赖可能装不上。不阻断，只提醒。
%PYCMD% -c "import sys; sys.exit(0 if sys.version_info[:2] <= (3,12) else 1)"
if errorlevel 1 (
    echo.
    echo [提醒] 检测到 Python 3.13 或更高版本。
    echo        Flet 0.25 系列主要适配到 Python 3.12，
    echo        新版本上可能出现依赖装不上的情况。
    echo        如果打包报错，建议改用 Python 3.11 或 3.12 重试。
    echo.
    pause
)

REM ============================================================
REM  第 2 步：安装打包依赖
REM ============================================================
echo.
echo [1/4] 安装打包依赖，约 1 到 3 分钟...
echo.
%PYCMD% -m pip install --disable-pip-version-check -i https://pypi.tuna.tsinghua.edu.cn/simple "flet[all]==0.25.2" pyinstaller
if errorlevel 1 (
    echo.
    echo 国内镜像失败，改用官方源重试...
    %PYCMD% -m pip install --disable-pip-version-check "flet[all]==0.25.2" pyinstaller
)
if errorlevel 1 (
    echo.
    echo [错误] 依赖安装失败，请检查网络后重试。
    echo.
    pause
    exit /b 1
)

echo.
echo [2/4] 检查打包工具是否可用...
%PYCMD% -c "import flet.cli" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [错误] flet 装上了但调用不了。
    echo        请把上面的报错截图发给我。
    echo.
    pause
    exit /b 1
)
echo      OK

REM ============================================================
REM  第 3 步：看看有没有 Flutter，决定走哪条路线
REM
REM  之前报 "flutter command is not available in PATH" 就是
REM  因为脚本默认走路线 A，但你机器上没装 Flutter SDK。
REM  现在检测一下，没有就自动改走路线 B。
REM ============================================================
echo.
echo [3/4] 检测打包环境...

set "HAS_FLUTTER="
where flutter >nul 2>&1
if not errorlevel 1 set "HAS_FLUTTER=1"

if defined HAS_FLUTTER (
    echo     找到 Flutter SDK，走路线 A（原生打包）
    goto ROUTE_A
)
echo     没有检测到 Flutter SDK，自动走路线 B（PyInstaller）
echo     这条路不需要 Flutter，功能完全一样，只是产物稍大。
goto ROUTE_B

REM ============================================================
REM  路线 A：flet build windows（需要 Flutter）
REM
REM  注意两点：
REM  A. 用 python -c 直接调 flet.cli.main，不依赖 PATH，
REM     避免 "flet 不是内部或外部命令"
REM  B. 项目名必须用英文
REM     Flet 0.25 有个已知 bug，名字含中文会让生成的 exe
REM     启动时报 ImportError: No module named main。
REM     所以用英文打包，完成后再把 exe 改名成中文。
REM ============================================================
:ROUTE_A
echo.
echo [4/4] 开始原生打包，首次约 10 到 40 分钟...
echo.
if exist build rmdir /s /q build

%PYCMD% -c "import sys; from flet.cli import main; sys.argv = ['flet'] + sys.argv[1:]; main()" build windows --project lyrics_studio --product LyricStudio --org com.zxb
if errorlevel 1 goto PACK_FAILED

set "OUTDIR=build\windows"
if exist "build\windows\lyrics_studio.exe" ren "build\windows\lyrics_studio.exe" "歌词修改工作台.exe"
if exist "build\windows\lyrics-studio.exe" ren "build\windows\lyrics-studio.exe" "歌词修改工作台.exe"
goto PACK_DONE

REM ============================================================
REM  路线 B：flet pack（PyInstaller，不需要 Flutter）
REM
REM  产物在 dist\LyricStudio\ 目录下，是个文件夹，
REM  里面有 exe 和它依赖的 dll，必须整个目录一起分发。
REM ============================================================
:ROUTE_B
echo.
echo [4/4] 开始 PyInstaller 打包，约 2 到 8 分钟...
echo.
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

REM Windows 上 PyInstaller 只认 .ico 格式，传 .png 可能失败。
REM 所以优先用 icon.ico，没有再退回不带图标。
set "ICONARG="
if exist "assets\icon.ico" set "ICONARG=--icon assets\icon.ico"
%PYCMD% -c "import sys; from flet.cli import main; sys.argv = ['flet'] + sys.argv[1:]; main()" pack main.py --name LyricStudio %ICONARG% -y
if errorlevel 1 goto PACK_FAILED

REM 目录改成中文名，exe 保持英文。
REM 改名 exe 有概率让 bootloader 找不到依赖，改目录名则完全安全。
set "OUTDIR=dist\LyricStudio"
if exist "dist\LyricStudio" (
    if not exist "dist\歌词修改工作台" (
        ren "dist\LyricStudio" "歌词修改工作台"
        set "OUTDIR=dist\歌词修改工作台"
    )
)
goto PACK_DONE

REM ============================================================
REM  失败处理
REM ============================================================
:PACK_FAILED
echo.
echo ============================================================
echo   打包失败。请把上面的报错截图发给我。
echo.
echo   几个常见的排查方向：
echo.
echo   1. 杀毒软件拦截
echo      PyInstaller 生成的 exe 常被误报，
echo      先把杀毒软件关掉或加白名单再试一次。
echo.
echo   2. Python 版本太新
echo      Flet 0.25 主要适配到 Python 3.12，
echo      3.13 / 3.14 上可能装不上依赖，建议换 3.11 或 3.12。
echo.
echo   3. 路径里有中文或空格
echo      把整个项目挪到纯英文路径下，例如 C:\lyrics\
echo.
echo   4. 依赖不完整
echo      试试手动执行：  pip install "flet[all]==0.25.2" pyinstaller
echo.
echo   最省事的替代方案：
echo   把代码推到 GitHub，打一个 v1.0.0 标签，
echo   云端会自动帮你打包，本机什么都不用装。
echo ============================================================
echo.
pause
exit /b 1

REM ============================================================
REM  成功收尾
REM ============================================================
:PACK_DONE
echo.
echo ============================================================
echo    打包成功！
echo.
echo    产物在 %OUTDIR% 目录下。
echo.
echo    重要：请把 %OUTDIR% 这整个文件夹一起压缩，
echo    不要只拷那个 exe。它旁边还有 dll 等依赖文件，
echo    单独拿走 exe 是打不开的，这是最常见的失败原因。
echo.
echo    建议：右键 %OUTDIR% 文件夹，
echo          选 发送到 - 压缩文件夹，
echo          把得到的 zip 发给别人，解压后双击 exe 就能用。
echo ============================================================
echo.
if exist "%OUTDIR%" explorer "%OUTDIR%"

endlocal
pause
