@echo off
chcp 936 >nul 2>&1
title 歌词修改工作台
cd /d "%~dp0"
setlocal

echo ============================================================
echo.
echo      歌词修改工作台   一键启动
echo.
echo ============================================================
echo.

REM ---------- 第 1 步 找到 Python ----------
set "PYCMD="
where python >nul 2>&1
if not errorlevel 1 set "PYCMD=python"
if not defined PYCMD (
    where py >nul 2>&1
    if not errorlevel 1 set "PYCMD=py -3"
)
if not defined PYCMD (
    echo 没有检测到 Python，请先安装 Python。
    echo.
    echo 下载地址： https://www.python.org/downloads/
    echo 建议装 3.11 或 3.12，不要装 3.13。
    echo.
    echo 安装时一定要勾选 Add Python to PATH 这一项，
    echo 否则装完这里还是找不到。
    echo.
    pause
    exit /b 1
)

echo 第 1 步 / 共 3 步   找到 Python：
%PYCMD% --version
echo.

REM ---------- 第 2 步 建虚拟环境 ----------
if exist ".venv\Scripts\python.exe" (
    echo 第 2 步 / 共 3 步   虚拟环境已存在，跳过
) else (
    echo 第 2 步 / 共 3 步   首次运行，正在创建虚拟环境，请稍候...
    %PYCMD% -m venv .venv
    if errorlevel 1 (
        echo.
        echo 虚拟环境创建失败，可能是 Python 安装不完整。
        pause
        exit /b 1
    )
)
call .venv\Scripts\activate.bat
echo.

REM ---------- 第 3 步 装依赖 ----------
echo 第 3 步 / 共 3 步   正在安装依赖，首次约需 1 到 3 分钟...
python -m pip install --quiet --disable-pip-version-check -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
if errorlevel 1 (
    echo.
    echo 清华镜像失败，改用官方源重试一次...
    python -m pip install --quiet --disable-pip-version-check -r requirements.txt
)
if errorlevel 1 (
    echo.
    echo 依赖安装失败。请把上面的报错截图发给我。
    echo 也可以手动执行这两行看看具体原因：
    echo     .venv\Scripts\activate.bat
    echo     pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)
echo.

REM ---------- 启动 ----------
echo ============================================================
echo    启动成功，软件窗口马上弹出。
echo.
echo    使用提示：在顶部歌词模板卡片上向右滑动，
echo              可以查看版本号和作者联系方式。
echo ============================================================
echo.
python main.py

if errorlevel 1 (
    echo.
    echo 软件异常退出，上面是报错信息。
    echo 最常见的原因：Flet 版本不对。
    echo 请确认 requirements.txt 里写的是 flet==0.25.2
    echo.
)

endlocal
pause
