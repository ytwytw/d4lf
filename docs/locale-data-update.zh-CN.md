# 本地化数据更新检查

**简体中文** | [English](locale-data-update.md)

`src.tools.locale_data_check` 是生成的本地化数据的失败即关闭（fail-closed）门禁。请在生成某个本地化数据之后、审查或提交生成的文件之前运行它。它不会修改源检出或生成的资产。

## 生成 zhCN 候选

使用完整的 Companion 与 d4data 检出，以及经过验证的 D2Core 快照。快照命令会发现当前的 D2Core 构建，仅下载配对的词缀/威能/暗金/护符装备（Talisman）静态 JSON，验证每一个 `(key, id)`
对，强制各语言区域记录数相等并执行保守的每数据集记录下限，并写入精确的源哈希。当前的下限为每个语言区域 750 条词缀、250 条威能、200 件暗金物品和 500 条扁平化护符装备记录。因此，合法的源数据收缩需要经过明确的政策审查，而不是静默地淘汰装备。该命令不会访问规划器或游戏客户端。

```powershell
uv run python -m src.tools.d2core_data `
    --output-dir C:\temp\d4lf-d2core
```

先生成到一个临时目录；`--allow-unresolved` 允许生成诊断输出，但不会设置
`runtime_ready`，也不会削弱发布检查器。

```powershell
uv run python -m src.tools.generate_zhcn_assets `
    --companion-repo C:\path\to\Diablo4Companion `
    --d4data-repo C:\path\to\d4data `
    --d2core-dir C:\temp\d4lf-d2core `
    --en-us-dir .\assets\lang\enUS `
    --zhcn-grammar .\assets\lang\zhCN\grammar.json `
    --reviewed-overrides .\src\tools\data\reviewed_zhCN.json `
    --output-dir C:\temp\d4lf-zhcn\lang\zhCN `
    --catalog-dir C:\temp\d4lf-zhcn\catalog `
    --allow-unresolved
```

如果不带 `--allow-unresolved`，只要候选尚未达到发布就绪状态，该命令就返回 `1`。输入无效或不可读时返回 `2`。生成器绝不会用英文文本填充缺失的中文值。

`--reviewed-overrides` 接受经过规范化、可安全发布的稳定 ID 翻译。该文件不得包含捕获哈希、游戏构建、时间戳、UUID、记录数或其他证据元数据。未知的稳定
ID、空翻译、ASCII 占位符以及 `evidence` 字段都会导致生成失败。公共映射文件的哈希会写入本地化清单以保证可复现性。该哈希基于规范化（canonical）JSON 内容计算，因此内容等价的
LF 与 CRLF 文件具有相同的哈希。

翻译优先级为：已审查覆盖、配对的 Companion 游戏数据，然后在配对游戏数据没有翻译时以 D2Core 作为补充。任何来源都不会因为缺席而成为权威：某个稳定 ID 若未出现在当前
D2Core 快照中，绝不会被从源清单中移除，也绝不会导致已有的非空中文别名在运行时被禁用。每条生成的本地化记录都包含一个 `translation_source`，记录其提供者、源身份和翻译哈希；D2Core
记录还包含配对源记录的哈希。提供者之间的分歧会保留在 `quality-report.json.translation_conflicts` 中，并在被明确审查之前阻止发布。源清单包含一个派生的
D2Core 翻译记录索引，发布检查器要求每个被选用的 D2Core 源 ID、源记录哈希、翻译哈希和数据集命名空间都与该索引匹配。D2Core/d4data
构建不一致仅允许用于诊断性候选生成，并强制 `runtime_ready` 保持为 false。

## 命令

所有输入路径都是显式的，因此同一个检查器既能在本地检出也能在 CI 中工作：

```powershell
uv run python -m src.tools.locale_data_check `
    --source-lock path/to/source-lock.json `
    --build-version path/to/d4data/buildVersion.txt `
    --locale-manifest path/to/zhCN/manifest.json
```

使用 `--source-manifest path/to/source-manifest.json` 可覆盖锁定文件中存储的源清单路径。
仅当有意测试新的清单 schema 时才使用 `--schema-version N`。受支持的默认值是 schema
版本 1。

## 更新顺序

1. 更新 d4data 和 Companion 检出，并记录它们精确的提交和数据构建。
1. 获取一个新的有界 D2Core 快照。记录其发现的构建、八个源 URL、哈希以及已记录文档的署名状态；不要抓取或绕过交互式规划器。
1. 比较各提供者的构建。混合构建的候选可以被分析，但不能被晋升。
1. 重新生成源清单和源锁定，包括每个已声明源文件的哈希。
1. 从该锁定源重新生成目标本地化数据及其清单。哈希被记录之后不要再手工编辑生成的文件。
1. 确认 `excluded_historical_records` 保持为零。候选检查器拒绝任何非零值：提供者快照缺席只是诊断元数据，而不是淘汰或隐藏某个已本地化稳定 ID 的理由。
1. 使用显式路径运行检查器。当更新流程自动化时，将 JSON 报告保留为 CI 构件。
1. 只有当进程以退出码 0 结束且报告为 `"ok": true` 时，才审查或提交生成的数据。

## Schema 版本 1

字段名使用蛇形命名（snake case）。SHA-256 值是 64 个十六进制字符。构建版本逐字复制自
d4data 的 `buildVersion.txt`，不含其末尾换行。

源锁定可以内嵌 `records`，也可以锁定一个单独的源清单：

```json
{
  "schema_version": 1,
  "build_version": "3.1.0.72592",
  "source_manifest": {
    "path": "source-manifest.json",
    "sha256": "<sha256 of the exact source-manifest.json bytes>"
  },
  "files": [
    {
      "path": "json/enUS_Text/meta/StringList/example.stl.json",
      "sha256": "<sha256 of the exact d4data file bytes>"
    }
  ]
}
```

源锁定 `files` 数组中的路径相对于包含 `buildVersion.txt` 的目录。单独的源清单具有以下结构：

```json
{
  "schema_version": 1,
  "build_version": "3.1.0.72592",
  "records": [
    {
      "stable_id": "affixes:example",
      "text": "Example source text",
      "source_sha256": "<sha256 of the UTF-8 source text>"
    }
  ]
}
```

生成的本地化清单记录相同的稳定 ID 以及每个翻译所用的源哈希：

```json
{
  "schema_version": 1,
  "build_version": "3.1.0.72592",
  "locale": "zhCN",
  "source_manifest_sha256": "<sha256 of the exact source-manifest.json bytes>",
  "files": [
    {
      "path": "affixes.json",
      "sha256": "<sha256 of the exact generated file bytes>"
    }
  ],
  "records": [
    {
      "stable_id": "affixes:example",
      "text": "示例文本",
      "source_sha256": "<matching source record hash>",
      "translation_source": {
        "provider": "d2core",
        "source_id": "affix:Affix_Example:123:x1",
        "translation_sha256": "<hash of the selected Chinese text>",
        "source_record_sha256": "<hash of the paired enUS/zhCN source record>"
      }
    }
  ]
}
```

生成的文件路径相对于本地化清单。记录哈希使用以 UTF-8 编码的精确源文本，不做任何空白或
Unicode 规范化。文件和清单哈希使用磁盘上的精确字节。

## 检查

当以下任一检查失败时，该命令拒绝此次更新：

- 每个清单都使用预期的 schema 版本。
- 源锁定、源清单、生成的本地化清单与 d4data `buildVersion.txt` 一致。
- 被锁定的清单、已声明的源文件/生成文件、源文本哈希和逐记录源哈希都匹配。
- 每个被锁定的 D2Core 数据集都高于其声明的记录下限，enUS/zhCN 计数相等，且每个被选用的
  D2Core 翻译都与锁定的派生记录索引匹配。
- 源与本地化的稳定 ID 集合具有完整的一一对应覆盖。
- 不存在缺失的稳定 ID、仅在本地化中新引入的稳定 ID，或在任一清单中重复的稳定 ID。
- 每条本地化记录都有翻译文本，且包含 ASCII 字母的文本不是纯 ASCII。这可以捕获被复制的
  源占位符，例如 `Example source text`。

检查器刻意不提供 ASCII 例外开关。对于有意的首字母缩略词，请在其所在文本的上下文中翻译，或者在清单生成方解决数据政策，而不是静默削弱这道门禁。

## 输出与退出码

标准输出是一个 JSON 对象。`issues` 包含稳定的代码，例如 `build_mismatch`、`hash_mismatch`、
`missing_record`、`new_record`、`duplicate_record` 和 `ascii_placeholder`。`summary.issue_counts`
适合用于 CI 注解或更新看板。

| 退出码 | 含义                                               |
| ------ | -------------------------------------------------- |
| `0`    | 所有检查通过。                                     |
| `1`    | 输入可读，但验证发现的问题使本次本地化更新不安全。 |
| `2`    | 参数或输入缺失、不可读、格式错误或结构无效。       |

将每个非零退出码都视为阻塞。特别地，退出码 2 不是被跳过的检查；它意味着检查器无法确认此次更新是安全的。

## 候选与赛季检查

已提交的 `zhCN` 数据包在其质量报告仍声明存在未解决记录的同时，支持受防护的交互。此命令验证每个发布门禁
`missing_record` 都在该报告中一一对应地声明：

```powershell
uv run python -m src.tools.locale_candidate_check `
    --source-lock .\assets\catalog\source-lock.json `
    --build-version .\assets\catalog\d4data-buildVersion.txt `
    --locale-manifest .\assets\lang\zhCN\manifest.json `
    --quality-report .\assets\lang\zhCN\quality-report.json
```

候选一致性不是发布批准。晋升仍然要求 `locale_data_check` 本身返回零，且清单包含 `"runtime_ready": true`。

生成器将有意排除的非装备物品类型记录在 `quality-report.json.scope` 中。它们仍以空别名保留在运行时物品类型
JSON 中，使历史英文配置键保持稳定，但它们不是源清单的要求，也不能阻塞 zhCN 装备里程碑。

定时源监视器将锁定的 d4data 与 D2Core 构建以及所有已声明的源哈希，与当前公开的上游字节进行比较：

```powershell
uv run python -m src.tools.season_data_watch `
    --source-manifest .\assets\catalog\source-manifest.json
```

它只下载 `buildVersion.txt`、已声明的 Companion 文件、用于构建发现的 D2Core 站点包，以及八个被锁定的
D2Core 静态 JSON 文件。任何构建或文件漂移返回 `1`；网络、清单或编码错误返回 `2`。
