@echo off
chcp 936 >nul 2>&1
title 环境检测
cd /d "%~dp0"

echo ============================================================
echo      环境检测   把下面这些内容截图发给我
echo ============================================================
echo.

echo [1] 当前代码页
chcp
echo.

echo [2] Python 版本
python --version 2>&1
if errorlevel 1 echo     【上面没有版本号就是没装 Python，或没勾 Add Python to PATH】
echo.

echo [3] py 启动器
py --version 2>&1
echo.

echo [4] pip 版本
python -m pip --version 2>&1
echo.

echo [5] 当前目录
cd
echo.

echo [6] 目录里有没有关键文件
if exist main.py (echo    main.py          有) else (echo    main.py          缺失！)
if exist requirements.txt (echo    requirements.txt  有) else (echo    requirements.txt  缺失！)
if exist src (echo    src 目录         有) else (echo    src 目录         缺失！)
echo.

echo [7] requirements.txt 的内容
type requirements.txt 2>&1
echo.

echo [8] 中文显示测试
echo    如果你能看清这行中文，说明编码没问题。
echo.

echo ============================================================
echo    检测完毕，请截图上面的内容。
echo ============================================================
echo.
pause
