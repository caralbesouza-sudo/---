# 海岛奇兵自动打螃蟹脚本-萝卜
必备：
```
1.下载雷电模拟器9.调整分辨率1280x720，打开海岛至地图上可以看到紫色螃蟹的那个界面，注意，不是开始进攻的界面
2.目前号上最好有瞬时，我嫌麻烦取消了钻石补兵的功能，之后有时间了可以发布2.0
3.vs自己配好环境，不会的就问问豆包，很简单，在auto_crab.py这个里面点击右上角的开始即可
4.有需要声呐脚本的可以联系3146762436@qq.com,所有脚本都是免费开源的
5.提前上药，开雕刻，配兵按照自己的来，上兵时顺序的，老黑带复活就行
```
## 当前稳健版用法

运行环境要求：Python 3.13、ADB 可执行文件可用、模拟器序列号默认为
`emulator-5554`，游戏截图必须是 `1280x720`。依赖安装：

```powershell
python -m pip install -r requirements.txt
```

默认会连续进攻，直到没有剩余进攻次数。钻石加速功能已经从主流程完全取消：

```powershell
python src\auto_crab.py
```

首次运行建议先做只读检查（会截图识别，但不会点击）：

```powershell
python src\auto_crab.py --check
```

显式指定连续进攻（和默认行为相同）：

```powershell
python src\auto_crab.py --loop
```

只进攻一次：

```powershell
python src\auto_crab.py --once
```

完成 3 次进攻后自动暂停（该参数会自动启用连续模式）：

```powershell
python src\auto_crab.py --pause-after 3
```

如果 `adb devices` 显示的序列号不是 `emulator-5554`：

```powershell
python src\auto_crab.py --device 你的设备序列号 --check
```

离线回归测试不会连接模拟器，也不会点击游戏：

```powershell
python -B -m unittest discover -s tests -v
```

运行前会检查 ADB 截图、分辨率和必需模板。流程中会识别并连续关闭博士
多页对话；螃蟹入口使用紫色主体与几何形状联合检测，普通 NPC 基地即使
模板分数较高也不会点击。异常截图保存在 `screenshots\errors`。

## 运行入口

```text
src\auto_crab.py
```

运行前把游戏停在能看到螃蟹入口和左下角兵种卡的海岛地图界面。当前版本按 `1280x720` 画面调试；设备号可用 `--device` 指定。

## 当前流程

```text
1. 识别并点击螃蟹入口
2. 进入螃蟹进攻界面
3. 在世界地图上、进入螃蟹前截取左下角兵力快照
4. 判断剩余进攻次数
5. 点击攻击
6. 点击确认攻击
7. 进入战斗，按“左下方 → 正下方 → 右下方”的顺序移动视角并识别海滩登陆点
   - 所有方向统一验证黄黑岸线、下方连续灰色滩面、滩面外侧海水的相邻关系
   - 排除战斗详情面板、兵种卡、技能按钮，点击点周围须有足够的滩面余量
   - 连续两帧定位稳定后才下兵；模板匹配框中心不再直接作为登陆坐标
   - 后一帧优先复核上一帧的落点：仍在有效登陆带内部且留有边缘余量时保持该点，避免浪花导致最高分点左右跳动
   - 选中英雄后重新截图定位，复核失败时停止，不点击之前的旧坐标
   - 未找到可靠登陆带时继续拖动视角
8. 固定顺序下兵
9. 按节奏释放英雄技能和机器小怪
   - 等待期间后台检查是否已经结算
   - 检测到结算后立即停止继续放技能
10. 识别结算返回按钮并返回
11. 识别并连续跳过博士多页对话，确认地图恢复
12. 执行普通补兵
    - 点击普通补兵图标 reinforce_icon.png
    - 点击“补充兵力” replenish_troops_text.png
13. 如果没有识别到普通补兵入口
    - 等待检测窗口结束后跳过补兵
    - 连续模式下直接进入下一轮攻击
14. 不检测、不点击任何钻石加速入口
15. 达到 `--pause-after` 设置的进攻次数后自动暂停
16. 未达到暂停次数时先识别世界地图上的螃蟹；找到则不移动，未找到才向右下方移动一次视角
17. 重新识别并进入螃蟹进攻界面
```

## 常用参数

运行模式、自动暂停次数和设备号请使用本说明开头列出的命令行参数；运行
`python src\auto_crab.py --help` 可以查看完整选项。默认连续模式和暂停次数定义在
`src\auto_crab.py` 顶部，战斗技能时间等高级参数在文件底部：

自动暂停开关：

```python
PAUSE_AFTER_STAGES = None  # None 表示不按次数暂停；也可设置为 3、5 等正整数
```

战斗技能节奏：

```python
battle_attack_profile.FIRST_HERO_SKILL_SECONDS = 10
battle_attack_profile.FIRST_ROBOT_SKILL_SECONDS = 5
battle_attack_profile.NEXT_HERO_SKILL_SECONDS = 10
battle_attack_profile.NEXT_ROBOT_SKILL_SECONDS = 5
battle_attack_profile.ROBOT_HERO_CYCLE_ROUNDS = 6
```

## 调试入口

优先使用 `--check` 做无点击检查，并使用 `python -B -m unittest discover -s tests -v`
运行录制截图回归测试。异常运行现场会自动写入 `screenshots\errors`。

## 核心文件

```text
src\auto_crab.py                 总控流程
src\battle_attack_profile.py     战斗下兵与技能释放
src\troop_status.py              左下角兵力快照与无损判断
src\template_click.py            螃蟹入口识别
src\click_attack_button.py       攻击按钮与次数识别
src\click_confirm_attack.py      确认攻击
src\click_result_return.py       结算返回
src\click_reinforce.py           普通补兵入口识别
src\click_replenish_troops.py    “补充兵力”按钮
src\skip_doctor_dialog.py        跳过博士对话
```

## 必需图片

运行依赖模板目录：

```text
screenshots\templates
```

不要删除这个目录。

## 可清理内容

以下内容属于调试或旧流程资产，不影响当前第一版主流程：

```text
screenshots\errors
screenshots\raw
screenshots\beach_samples
configs
src\__pycache__
src\match_beach.py
src\record_clicks.py
src\replay_clicks.py
src\test_view_swipe.py
```

这些内容可以手动删除；模板目录 `screenshots\templates` 需要保留。

## 已知限制

- 依赖固定分辨率和模板匹配。
- 战斗打法是固定下兵和固定技能节奏，不会按阵型智能调整。
- 海滩颜色识别参数是根据当前 1280×720 截图校准的；游戏地图皮肤或模拟器显色明显变化时，需用新调试图再校准。
- 普通补兵后不会使用钻石加速，也不会等待自然训练完成。
- 世界地图通过菜单和回基地按钮判断，不再要求左下角有足够多兵种卡片。补兵流程清除博士对话后直接检测普通补兵图标：出现就补兵，等待超时未出现则继续攻击；不会点击钻石加速。
- 如果游戏 UI 位置变化，需要重新截模板或调整搜索区域。
