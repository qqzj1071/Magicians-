# 构筑旧规则：已过时

obsolete-deckbuilding-pre-v1.0.zip保存构筑v1.0冻结前规则、候选、报告及shared-draft原始实验。包内manifest保留原路径与SHA-256；逐文件读取验证后才移除工作副本，校验记录为obsolete-deckbuilding-pre-v1.0-verification.json。默认不解压、不检索、不作为当前规则；只在用户明确要求追溯时恢复指定文件到独立目录，禁止覆盖现行数据。

当前唯一构筑规则：[构筑v1.0](../releases/deckbuilding-v1.0/README.md)。卡牌版本独立保持releases/v1.0/cards.json。

# 历史封存

GitHub仓库以三个`pre-v1.0.zip.part*`分卷保存完整归档，`volumes.json`记录各卷与合并文件的大小及SHA-256。本地原始ZIP保留但不重复提交。确需追溯历史时，先运行`python tools/restore_history.py`重建并校验ZIP；该命令不会解压或覆盖当前卡表。日常工作不需要重建归档。

pre-v1.0.zip为去重压缩归档；manifest.json保存原始相对路径、大小与SHA-256，objects/按内容哈希存储。所有内容已解压校验后才移除工作副本。默认不读取或解压。

只有用户明确要求追溯时，才用zipfile按manifest定位指定object并恢复到单独目录；不要覆盖当前卡表。验证信息见verification.json。
