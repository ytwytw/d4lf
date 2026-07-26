# 符印编辑器的词缀/地下城类别拆分，以支持全局词缀黑名单（#502）

**简体中文** | [English](0003-sigil-editor-affix-dungeon-kind-split.md)

符印配置文件编辑器此前以地下城为中心：每一行符印规则都渲染一个 "Dungeon:" 选择器加一个条件列表，因此用户无法表达"在所有符印上屏蔽这个词缀"——一条全局的、与地下城无关的规则。过滤器本身已支持此类规则（`_match_affixes_sigils` 在符印包含指定词缀时匹配，无论其地下城是什么），但编辑器无法编写或加载这些规则，并且会在遇到顶层词缀名时抛出 `KeyError`。

## 决定

编辑器将每条符印规则归类为一个 `kind` —— `affix` 或 `dungeon` —— 并据此渲染。`kind` 是**由名称推导**的，而不是存储的：

- `derive_sigil_kind(name)` 在名称存在于 `sigils.json` 的 dungeons 映射中时返回 `dungeon`，否则返回 `affix`。不新增配置文件字段；现有配置文件加载不变。
- `sigil_name_dict_for_kind(kind)` 按类别选择名称池（affix = minor+major+positive；dungeon = dungeons）。
- **affix 类别**的行是该词缀的全局黑名单/白名单，只渲染 "Affix:" 选择器——条件列表和 Add/Remove Condition 控件会被隐藏，因为条件是地下城范畴的概念。
- **dungeon 类别**的行保留现有的 "Dungeon:" 选择器加条件列表，不变。
- `CreateSigil` 暴露一个 Kind 下拉框（dungeon/affix），用于重新填充名称池。

名称校验保持宽松：`SigilConditionModel.name_must_exist` 检查名称是否在合并后的 affix+dungeon 字典中，不按类别强制限定名称池。

## 影响

- 无 schema 变更，无迁移；通过现有的 `SigilConditionModel`（`{name, condition}`）往返不变。
- 同时出现在两个名称池中的名称存在歧义，会解析为 `dungeon`（先检查 dungeons）。已接受：当前数据中不存在重叠。
- 由于校验宽松，被错误分类的名称不会在加载时被拒绝；这是用严格性换取零向后兼容风险。
- 此修复是符印稀有度 GUI 控件（ADR-0002）的前置条件，后者会在同一个选项卡中添加稀有度行。
