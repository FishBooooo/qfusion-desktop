# ADR-0002：Tauri 2 + FastAPI Sidecar

- 状态：Accepted
- 日期：2026-07-27

## 背景

应用需要 Windows 原生安装体验、React 金融界面和成熟的 Python 数据/研究生态，同时不能要求用户安装 Python、Node 或 Docker。

## 决策

使用 Tauri 2 承载 React + TypeScript 前端，使用经 Nuitka standalone 打包的 FastAPI 进程作为 Sidecar。正式运行时：

- Tauri 启动和监督 Sidecar；
- Sidecar 仅绑定 `127.0.0.1` 的随机端口；
- 每次启动使用新的临时会话令牌；
- 前端使用精确来源和令牌访问 API；
- Sidecar 支持健康检查、优雅退出、崩溃恢复和单写入实例保护。

## 后果

优点是安装体积和资源占用低于 Electron，且保留 Python 研究生态。代价是需要处理跨进程握手、版本兼容、二进制打包和 Windows 杀毒软件误报验证。

## M0 说明

M0 使用固定开发端口演示健康通信，Tauri 空壳和 Python 后端分别构建。动态端口、令牌和 Sidecar 绑定在后续专门实现并测试。
