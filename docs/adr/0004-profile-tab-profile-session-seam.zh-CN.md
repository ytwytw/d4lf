# ProfileSession 统一承接 Profile 编辑器的持久化

[English](0004-profile-tab-profile-session-seam.md)

`profile_tab.py` 和 `profile_editor.py` 原本都直接调用 `ProfileDocumentStore` 与
`IniConfigLoader`。`ProfileEditor.save_all()` 还同时负责验证、“验证后模型发生变化”的
警告对话框以及成功/错误对话框。

新增的 `ProfileSession` 模块通过单一接口负责发现、加载、保存（验证并持久化）和脏状态
检查。它返回结果类型（`Loaded`/`YamlError`/`EmptyError`/`ValidationError` 与
`Saved`/`ValidationDiffers`/`Failed`），而不是抛出异常。`ProfileEditor` 不再接触
`ProfileDocumentStore` 或显示对话框，只公开 `get_current_model()`。`ProfileTab` 负责
所有警告、信息、错误和关闭确认对话框，并在用户确认后决定是否用 `force=True` 重试保存。

最近打开的 Profile 通过注入的 `ProfileLastOpenedStore` 协议持久化，而不是直接使用
`QSettings`，因此 `ProfileSession` 不导入 PyQt，也可以脱离 Qt 控件进行测试。

曾考虑保留 `ProfileEditor.save_all()`，只包装 `profile_tab.py` 的现有调用；但这会让
真正的持久化逻辑仍重复存在于两个文件中，也无法把“验证后不同”的对话框收拢到一个清晰边界。
