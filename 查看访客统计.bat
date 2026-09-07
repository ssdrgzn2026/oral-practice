@echo off
chcp 65001 >nul
title MiscHub 访客统计
echo 正在从服务器获取访客统计……
echo.
ssh root@oral.pingxu.xin "python3 /opt/oral-practice/scripts/stats_report.py"
echo.
pause
