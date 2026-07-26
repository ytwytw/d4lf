# 如何向这些文件添加内容

**简体中文** | [English](How%20to%20add%20to%20these%20files.md)

这些文件全部根据 d4data 的数据自动生成。
对它们所做的任何手动添加都会在下次数据更新时被覆盖。

如果你想向这些文件添加数据，请按以下步骤操作：

1. 下载最新版本的 d4data：https://github.com/DiabloTools/d4data.git
1. 运行 [gen_data.py](../../../src/tools/gen_data.py)。你需要提供上述下载内容的路径。例如，
   你可以运行：`python gen_data.py C:\path\to\d4data`

如果没有看到你期望的新数据，你需要将其添加到位于
[src/tools/data/custom_enUS.json](../../../src/tools/data/custom_enUS.json) 的自定义覆盖文件中。该文件存储了
我们因各种原因未能在 d4data 中找到的任何额外数据。

自定义文件是一个以目标文件名命名的单个 JSON 对象。例如：

```json
{
    "affixes": { "mana_per_second": "mana per second" },
    "charms_affixes": { "lucky_hit_up_to_a_chance_to_deal_holy_damage": "lucky hit up to a chance to deal holy damage" },
    "seals_affixes": { "maximum_resolve": "maximum resolve" },
    "aspects": ["aspect_of_inner_calm"],
    "sigils": {
        "dungeons": { "aldurwood": "aldurwood" },
        "major": { "death_pulse": "death pulse" },
        "positive": { "reduce_cooldowns_on_kill": "reduce cooldowns on kill" }
    },
    "uniques": { "harlequin_crest": { "num_inherents": 2 } },
    "sets": ["arms_of_arreat"],
    "tributes": { "tribute_of_radiance": "tribute of radiance" },
    "item_types": { "HoradricSeal": "horadric seal" },
    "tooltips": { "ItemPower": "item power" }
}
```

每个区块的结构必须与其扩展的目标文件一致（列表或对象）。不存在的区块会被静默跳过。

唯一的例外是 corrections.json，它可以直接修改。如果你发现某个暗金装备的 TTS 名称有误，就在那里修复。

添加自定义数据后，再次运行 gen_data，并确认生成的资产文件符合你的预期。然后提交一个 PR。
