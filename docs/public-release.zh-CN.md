# 公开发布安全

**简体中文** | [English](public-release.md)

不要更改私有开发仓库的可见性，也不要镜像其 `.git` 目录。仓库中的自定义提交作者、分支名、远程
URL、reflog 和时间戳都可能识别出开发账号。请在一个由 Git 归档构建的独立 Git 仓库中准备发布。可以
选择只保留公开上游历史的署名 fork 发布，或者使用全新历史的独立发布。

## 隐私边界

仓库扫描器会拦截常见凭据、非占位符电子邮件地址、绝对 home 路径、私有采集指纹、原始 JSONL、日志、
录像、采集目录中的截图、崩溃/网络转储、数据库、归档文件和发布二进制文件。`.public-safety.local`
用于添加私有字面量片段，而不会提交或打印它们。复制 `.public-safety.local.example`，然后添加绝不
能离开开发机器的账号句柄、姓名、电子邮件、机器名和 home 路径片段。

只有通用扫描器实现和合成测试会被跟踪，以便钩子（hooks）和 CI 执行同一策略。扫描器报告、SARIF
输出、密钥基线、发现的值以及本地拒绝列表都会被忽略，并且必须留在仓库之外。

只有经过规范化并审查的本地化字符串才允许被跟踪。原始采集、采集哈希、会话 UUID、逐会话的时间戳
和清单、视频、截图以及回放报告都必须留在 Git 之外。不含身份信息的聚合覆盖率统计数据可以在审查
后被跟踪。已审查的映射不得声称其来源采集是公开可用的。

公开 build-planner URL 及其公开分享代码可以作为可复现的集成夹具被跟踪。除非链接的 build 本身
包含个人或可识别账号的文本，否则它们不被视为私有采集数据。

这保护的是仓库内容和 Git 元数据。它无法让通过个人拥有的 GitHub 账号进行发布的行为匿名化：账号、
组织成员关系、账单、IP 记录以及后续互动仍可能关联到发布者。GitHub fork 会有意将发布归属于该账号。
当需要账号不可关联性时，请使用真正独立的组织或化名账号，不要创建 GitHub fork，也不要复用私有
仓库的提交哈希或远程地址。

## 第三方数据门槛

生成的 zhCN 语言包含有源自 Diablo4Companion、DiabloTools/d4data 和 D2Core 的数据。导出命令要求具备
`THIRD-PARTY-NOTICES.md`、`docs/third-party-data.md` 中的署名政策、README 中的来源致谢，以及 D2Core
的机器可读 `documented` 状态。重新生成的来源清单必须保留 documented 状态和技术出处。

## 署名 fork 流程

当发布者接受其 GitHub 账号与项目之间的公开关联时，使用此流程。准备脚本通过选定的 V9 基线保留公开
上游历史，然后使用配置的 GitHub 身份写入恰好一个压缩（squashed）发布提交。它不会复制私有开发
提交、分支、reflog、远程、被忽略的文件或不可达的 Git 对象。

1. 将 `user.name` 配置为预期的公开 GitHub 名称，将 `user.email` 配置为 GitHub 提供的
   `@users.noreply.github.com` 地址。

1. 填充被忽略的 `.public-safety.local` 拒绝列表。

1. 验证所有第三方声明和 D2Core 机器可读发布状态。

1. 验证 README 支持链接、`CODEOWNERS` 和发布通知工作流属于发布身份；不要继承上游的所有权或
   webhook 配置。

1. 运行 `uvx prek run --all-files` 和完整测试套件。

1. 提交私有开发源码，并验证工作区是干净的。

1. 运行
   `scripts/prepare_fork_release.ps1 -TargetPath <empty-directory-outside-this-repo> -BaseRevision v9.3.7`。

1. 在准备好的目录中，验证分支、直接父提交、作者、干净的归档内容以及不存在远程：

   ```powershell
   git status --short --branch
   git log --format=fuller -2
   git remote
   ```

1. 创建 GitHub fork，仅在准备好的目录中添加 fork 远程，并推送 `zhcn-v9`。

准备好的仓库故意没有远程。由发布者决定何时将其连接到 GitHub fork。

## 独立发布流程

1. 填充被忽略的 `.public-safety.local` 拒绝列表。
1. 验证所有第三方声明和 D2Core 机器可读发布状态。
1. 验证 README 支持链接、`CODEOWNERS` 和发布通知工作流属于发布身份；不要继承上游的所有权或
   webhook 配置。
1. 运行 `uvx prek run --all-files` 和完整测试套件。
1. 提交私有开发源码，并验证工作区是干净的。
1. 运行 `scripts/export_public_repo.ps1 -TargetPath <empty-directory-outside-this-repo>`。
1. 在导出的目录中，验证 `git rev-list --all --count` 输出 `1` 且 `git remote` 无任何输出。
1. 在预期的发布身份下创建一个空的、非 fork 的 GitHub 仓库，然后仅从导出的目录添加其远程。

独立导出脚本绝不删除已存在的目标，绝不复制被忽略的文件，使用中性的作者和提交者，将提交时间戳
固定为 UTC，并故意不创建远程。
