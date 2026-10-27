# Windows 免安装发布

正式试玩包是完整文件夹 ZIP，解压后双击 Magicians.exe。无需 Godot 编辑器、Python 安装器、.NET SDK、管理员权限或联网。保留 exe、pck、data_Magicians!_windows_x86_64 和 runtime-data 的相对位置。可双击 Create-Desktop-Shortcut.vbs 创建快捷方式；移动游戏文件夹后需重建快捷方式。

运行时资源从 exe 旁 runtime-data 读取，设置和日志写入 Godot 的 user:// 用户目录。优先使用包内 Python，移除继承的 PYTHONHOME、PYTHONPATH；不从玩家电脑下载或执行未经发布测试的解释器。包内 Python 固定为发布测试通过的 3.12.10 amd64，.NET 为自包含运行时。Godot 使用 Compatibility 渲染，支持 Windows 10/11 x64。

发布包包括现行 252 张 v1.0 卡牌 DOCX、第三方许可、启动完整性清单和外部 SHA-256 清单。启动时校验 EXE、PCK、程序集和运行数据；文件缺失或修改时拒绝启动并说明原因。清单不参与自身校验。文件只读属性只是误改保护，可以被文件所有者取消；公开哈希清单也可被主动攻击者改写。该机制不能防内存修改、替换程序或联机作弊。联机版本必须由可信服务器验证规则、命令和结果。

构建需显式运行 tools/installer/build_portable.py，不注册提交钩子、后台更新或定时打包。新的代码提交不会改变已交付的发布包。构建参数与第三方运行时来源必须保存在 BUILD-INFO.json 中。保留原卡牌与 AI 模型哈希，不将未提交的 v1.1 平衡实验带入 v1.0。

验收需要在带中文和空格的新目录解压，从无关工作目录运行，清空开发工具 PATH 并故意设置无效 Python/.NET 环境变量，执行 --headless -- --release-smoke 验证至少两轮四场 AI 对局。还需修改一个受校验数据文件并确认启动拒绝，最后核对解压包清单。当前机器隔离验证不能替代另一台实体电脑上的测试。

未进行代码签名的发布包可能被 Windows SmartScreen 提醒，正式公开发行应申请代码签名。不要建议玩家全局关闭安全软件。每次修改发布内容必须重新计算 SHA-256。

