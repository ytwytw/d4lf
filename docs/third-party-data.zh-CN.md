# 第三方数据

**简体中文** | [English](third-party-data.md)

本文件记录生成或捆绑数据的发布要求，这些数据的出处独立于 D4LF 的 MIT 软件许可证。

## D2Core

**公开再分发状态：documented。**

zhCN 目录和生成的语言包含有源自 D2Core 公开静态数据端点的规范化记录。项目所有者已确认，这些
数据可以被本项目直接使用、规范化、捆绑和公开再分发。公开发布必须在 README 中致谢 D2Core，并在
生成的清单中保留来源 URL、来源 build 标识符和哈希。此署名不代表 D2Core 对 D4LF 或其发布的认可。

受影响的生成路径包括：

- `assets/catalog/source-manifest.json`
- `assets/catalog/source-lock.json`
- `assets/lang/zhCN/*.json`

机器可读状态为 `documented`；重新生成不得在未经声明的情况下将其改回 `unverified`。

## Diablo4Companion

主要的稳定 ID `enUS`/`zhCN` 配对源自
[Diablo4Companion](https://github.com/josdemmers/Diablo4Companion)，该项目按 MIT 许可证分发。
公开源码树和二进制发布归档必须包含 `THIRD-PARTY-NOTICES.md`，其中包括上游版权和许可声明。

## DiabloTools d4data

游戏 build 标识符和稳定的内部元数据会与
[DiabloTools/d4data](https://github.com/DiabloTools/d4data) 交叉核对，该项目按 MIT 许可证分发。
公开源码树和二进制发布归档必须在 `THIRD-PARTY-NOTICES.md` 中包含其上游版权和许可声明。直接的
《暗黑破坏神 IV》游戏文本和素材仍是暴雪娱乐（Blizzard Entertainment）的财产。
