# ProfileSession 作为配置文件编辑器持久化的前置接口

**简体中文** | [English](0004-profile-tab-profile-session-seam.md)

`profile_tab.py` 和 `profile_editor.py` 此前都直接与 `ProfileDocumentStore`
和 `IniConfigLoader` 交互，且 `ProfileEditor.save_all()` 还负责校验、
"校验后模型有差异"警告对话框以及成功/错误对话框。我们引入了一个
`ProfileSession` 模块，在单一接口背后统一负责发现、加载、保存（校验 +
持久化）和脏状态检查，并返回结果类型
（`Loaded`/`YamlError`/`EmptyError`/`ValidationError`，`Saved`/`ValidationDiffers`/`Failed`）
而不是抛出异常。`ProfileEditor` 不再接触 `ProfileDocumentStore`，也不再显示
任何对话框——它只暴露 `get_current_model()`。`ProfileTab` 拥有所有对话框
（警告、信息、错误、关闭确认），并决定是否在用户确认后以
`force=True` 重试保存。最近打开配置文件的持久化通过一个注入的
`ProfileLastOpenedStore` 协议进行，而不是直接使用 `QSettings`，因此
`ProfileSession` 不含任何 PyQt 导入，可以在没有 Qt 控件的情况下测试。

我们考虑过保留 `ProfileEditor.save_all()` 原样，只包装
`profile_tab.py` 中的现有调用，但那会让真正的持久化逻辑
分散重复在两个文件中，而"校验后有差异"对话框仍困在
编辑器内部，而非收拢到一个狭窄的接缝之下。
