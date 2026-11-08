# 三刃使徒 Wiki

收录《密教模拟器》（Cultist Simulator）三部使徒 Mod 的本地 MediaWiki 资料库：

- **蔑世使徒** / Apostle Contemnant
- **破军使徒** / Apostle Proterant
- **坚毅使徒** / Apostle Obdurant

> [!NOTE]
> **使用提示**  
> 这个 Wiki 主要是用来**方便检索和查阅 Mod 文本与底层数据**（卡牌台词、行动逻辑、结局文本、数值等）的。  
> 里面的引导和“教程”部分基本都是 **AI slop**，没有多少看的意义，建议直接忽略，纯当数据字典和文本索引查阅即可。

---

## 快速访问

- **访问地址**：[http://localhost:8090/](http://localhost:8090/)
- **管理员账号**：`WikiAdmin`（密码见根目录 `.env` 文件中的 `WIKI_ADMIN_PASSWORD`）

---

## 启动与常用命令

需要先安装 **Docker Desktop**。

### 一键启动
直接双击运行根目录下的 **`启动Wiki.bat`** 即可（会自动检测 Docker 运行状态、启动服务并在浏览器中打开页面）。

### 命令行管理
在 PowerShell 中使用 `tools/wiki.ps1` 进行管理：

```powershell
# 启动 Wiki
pwsh -File tools/wiki.ps1 -Action start

# 停止 Wiki
pwsh -File tools/wiki.ps1 -Action stop

# 查看运行状态
pwsh -File tools/wiki.ps1 -Action status

# 备份数据库（备份文件存放在 backups/ 目录）
pwsh -File tools/wiki.ps1 -Action backup

# 重新生成并导入所有页面（更新 Mod 数据后使用）
pwsh -File tools/import-wiki.ps1

# 重新生成页面并同步导入媒体文件（图片/音频）
pwsh -File tools/import-wiki.ps1 -WithMedia
```

---

## 收录内容

全站页面均由 Mod 原始数据解析生成，收录内容包括：

| 内容分类 | 数量 | 说明 |
| :--- | :--- | :--- |
| **卡牌 (Elements)** | 1,381 | 卡名、卡面描述、性相、时限、槽位及对应卡图 |
| **行动 (Recipes)** | 1,453 | 触发条件、耗时、概率产出、后续行动链及结局触发 |
| **结局 (Endings)** | 21 | 结局全文本、结算画面及背景音频 |
| **成就 (Achievements)** | 28 | 成就图标、名称与解锁条件说明 |
| **牌组 & 行动槽** | 42 | 36 个卡池规则 + 6 个自定义行动槽 (Verbs) |
| **传承 (Legacies)** | 6 | 包含各 Mod 的起始传承与清除记录 |
| **性相与索引页** | 440+ | 性相持有者反查、分类索引与消歧页 |
| **原始 JSON 数据页** | 2,931 | 所有 Mod 实体对应的未转译底层数据页 |

站内还包含 790+ 个 Mod 本地配套的图片与音频资源。
