# 日志解析与入库脚本 使用说明 
## 背景

> 有一次，我翻开自己过去一个月写的 Markdown 日记（其实就是每天的to-do-list)，想算算每天到底花了多少时间在写代码、学习、运动和睡眠上，有没有严格按照计划执行，或者单纯想知道每天学了多少东西，做了什么事情......结果看着一堆散乱的文字就头大：根本没法快速统计，也没法对比计划和执行的差距。于是我突发奇想：要不写个脚本，把我的“Plan vs Actual/Yesterday”日记自动化解析，直接扔进数据库里？这样我就可以一键生成各种报表，随时查看自己在哪些地方坚持得好，哪些地方拖了后腿，还能用标签做多维度分析——真正把零散的笔记变成可量化、可对照的数据。这个工具，就是为像我一样既想保留手写日记自由度，又想从日常生活和学习数据中发现不足、持续优化自我的人量身打造——让每一条记录，都成为下一步进步的助推器。  

---
## 一、简介

这个脚本提供一套“清单式 Markdown 日记”自动解析并批量写入 MySQL 的解决方案。你只需按照指定格式写好日记，运行脚本即可将每天的「Yesterday／Plan／Actual」三段记录结构化到数据库，无需手动整理。

这能帮你做什么  
- **自动化**：把“Plan”、“Actual/Yesterday” 三段式 Markdown 日记一键解析、清洗、写入 MySQL  
- **可量化**：自动算出每项活动的开始/结束时间、时长和完成情况  
- **可对比**：快速对比计划 vs 实际、发现拖延点和执行偏差  
- **可分析**：基于标签（如 `coding`、`sleep`、`exercise` 等）做多维度统计，驱动自我提升  

---

## 二、功能概览

* 按年月日目录自动定位、读取指定日期的 Markdown 日记
* 支持三大段落：`Yesterday`、`Plan`、`Actual`
* 动态匹配可选序号、跨午夜时间段、单点事件（起止相同）
* 多级类别（`.` 分隔），多重类别（`&` 分隔）
* 英文／中文冒号、反引号包裹、flag 标记（done/pending/…）
* 自动计算持续时长（单点事件 `duration=NULL`）
* 可选 `INSERT IGNORE` 跳过重复、支持唯一索引
* 命令行 & Python API 双模式调用，支持批量区间或单日导入

---

## 三、目录结构示例

```
日记/  
  └─ 2025-07/                ← 月度目录（YYYY-MM）
      └─ 2025-07-23/         ← 每日文件夹（YYYY-MM-DD）
          └─ 2025-07-23.md   ← 对应 Markdown 日记
scripts/
  └─ diary_loader.py        ← 解析 & 入库主脚本
README.md                   ← 本文件
```

---

## 四、环境与依赖

* **Python ≥ 3.7**
* **MySQL ≥ 5.6**（推荐 InnoDB 引擎）
* **pip 安装依赖**：

  ```bash
  pip install pandas sqlalchemy pymysql python-dateutil tqdm
  ```

---

## 五、日记格式规范

1. **文件命名**

   * 格式：`YYYY-MM-DD.md`
   * 路径：`ROOT_DIR/2025-07/2025-07-23/2025-07-23.md`

2. **YAML 头（可选）**

   ```yaml
   ---
   date: 2025-07-23
   timezone: Asia/Singapore
   ---
   ```

3. **段落标题**

   * 必须三段，且**用反引号或 `##`** 标注，段与段之间可以用任意字符分割：

     ```md
     `Yesterday`
     `Plan`
     `Actual`
     ```
   * 或

     ```md
     ## Yesterday
     ## Plan
     ## Actual
     ```

4. **记录行格式**

   ```
   [序号.] hh:mm[-hh:mm] [@]category1[.sub][&category2...] [:|：] 描述 [空白 flag]
   ```

   * **序号**：可选，形式 `1.`、`23.`，后可跟空格
   * **时间段**

     * `hh:mm-hh:mm`：标准区间
     * `hh:mm` 或 `hh:mm-hh:mm`（相同）：单点事件
     * 若 `end < start`，自动跨日
   * **类别**

     * 必须以 `@` 开头（可反引号包裹），如 `` `@meal.lunch&exercise.run` ``
     * 允许多级（`.`）与多重（`&`）
   * **冒号**：英文 `:` 或中文 `：`
   * **描述**：任意自然语言
   * **flag**（可选）

     * 五种枚举：`done` / `pending` / `planned-OnTime` / `planned-WrongTime` / `extra`
     * 可反引号包裹
     * 与描述之间可用 0+ 空白分隔

5. **示例日记**
```markdown
`Yesterday`
5. 23:27-02:00 `@chat.gran`:  聊天  `extra`
6. 02:00-03:00 `@leisure`: 刷视频     `extra`
7. 03:00-11:00 `@sleep`  : 睡觉       `planned-WrongTime`

---
`Plan`
1. 11:00-11:00 `@wakeup` : 起床                                 `pending`
2. 11:00-12:30 `@meal.lunch`   : 午餐                           `done`
3. 12:30-13:00 `@coding.sql` : 写一道 SQL                       `pending`
4. 13:00-15:00 `@coding.pandas` : Pandas 练习                   `pending`
5. 15:00-18:00 `@research.model.qmdj` : 改进模型                 `pending`
6. 18:00-20:30 `@exercise.run&shower.dinner`: 运动＋洗澡＋晚餐   `pending`
7. 20:30-23:00 `@leisure` : 自由安排                            `done`
8. 23:00-23:30 `@commute&routine` : 回寝室＋洗漱                `done`
9. 23:30-23:59 `@routine` : 准备睡觉                            `pending`

---
`Actual`
1. 11:00-12:30 `@meal.lunch`   : 午餐                                      `planned-OnTime`
2. 12:30-15:54 `@coding.leetcode.python` : LeetCode Python                 `extra`
3. 15:54-16:37 `@gaming` : 打游戏   `extra`
4. 16:37-18:49 `@coding.python.module-package` : Python module & package   `extra`
5. 18:49-19:48 `@study.python.question`  : Python 问答                     `extra`
6. 19:48-20:30 `@study.java`: java学习                                     `extra`
7. 20:30-20:49 `@coding.python.unknown` : Python LXF                       `extra`
8. 20:49-21:30 `@meal.dinner`   : 晚餐                                     `planned-WrongTime`
9. 21:30-23:59 `@gaming&shower&housework` : 打游戏＋洗澡＋收拾              `extra`
```
---

## 六、正则匹配逻辑

```python
PATTERN = re.compile(r"""
    ^\s*
    (?:\d+\.\s*)?                             # 可选序号
    (?P<start>\d{1,2}:\d{2})                  # start
    (?:-(?P<end>\d{1,2}:\d{2}))?              # 可选 end
    \s*                                        # 时间→类别的分隔，可有可无
    `?@?(?P<cat>[^\s:`]+)`?                # @category（可选反引号、@可选）
    \s*[：:]\s*                                # 英中冒号
    (?P<desc>.*?)                              # 描述非贪婪
    (?:\s+`?(?P<flag>done|pending|
                planned-OnTime|
                planned-WrongTime|
                extra)`?                      # 可选 flag（可反引号）
    )?                                         # flag 整块可选
    \s*$
""", re.VERBOSE)
```


「一行日记」要满足的 3 个硬条件，其余都随意：
```
[可选序号.] 开始-结束  @类别 [:] 描述  [可选 flag]
```

* **时间段**：`hh:mm` 或 `hh:mm-hh:mm`（结束比开始小就当跨天；如果两者相同就是单点事件）。
* **@类别**：单个 `@tag.sub&tag2` 就行；如果你懒得写 `@` 也没关系，脚本默认补。
* **flag**：`done / pending / planned-OnTime / planned-WrongTime / extra`，想写就写，前面留 1 个空格即可。

> 只记住一句：
> **“时间-类别-描述，flag 另起一个空格”**

---

## 七、数据库表结构与索引

```sql
CREATE TABLE diary_entries (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    date          DATE     NOT NULL,
    segment       ENUM('yesterday','plan','actual') NOT NULL,
    start_dt      DATETIME,
    end_dt        DATETIME,
    duration      INT,                      -- 单点事件为 NULL
    category      VARCHAR(255),             -- 多重类别用逗号分隔
    activity_flag VARCHAR(32),              -- done/pending/…/extra
    description   TEXT,
    raw_line      TEXT,
    UNIQUE KEY uniq_diary (date, segment, start_dt, end_dt)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

* **唯一索引**：防止重复插入。
* **注意**：`duration` 和 `end_dt` 可为 `NULL`，需在表定义允许。

---

## 八、脚本配置

在 `diary_loader.py` 顶部调整：

```python
ROOT_DIR   = Path(r"C:\Users\LFen\Nutstore\...\日记")    # 日记根目录
TABLE_NAME = "diary_entries"
MYSQL_URL  = "mysql+pymysql://user:pwd@host:3306/db?charset=utf8mb4"
```


---

## 九、使用方法

1. **命令行调用**

   * 单日（默认今天）：

     ```bash
     python diary_loader.py
     ```
   * 指定日期：

     ```bash
     python diary_loader.py --date 2025-07-23
     ```
2. **批量区间**（Bash/PowerShell 脚本或 Python 循环）。
3. **Python API**：

   ```python
   from diary_loader import load_day, write_mysql
   df = load_day(date(2025,7,23))
   write_mysql(df) #如果你不需要导入到mysql中也可以直接输出到excel表格，方法可以ai一下
   ```

---

## 十、常见问题与排查

1. **No parsable entries**

   * 检查段落标题是否写成 `` `Yesterday` `` 或 `## Yesterday`
   * 检查行是否符合正则（`@`、冒号、flag、空白分隔）
2. **跨日/单点事件**

   * 单点事件 (`start==end`) → `end_dt=start_dt`，`duration=NULL`
   * 跨日逻辑：仅当 `end < start` 时 `+1 day`
3. **flag 不匹配**

   * 未写 `done|pending|...` 或写错拼写可导致 `flag=None`
4. **多类别解析**

   * `cat.split("&")` → 逗号拼接，写库前可自定义分隔符
1. **重复报错 (IntegrityError)**

   * 可选 `method=upsert_ignore` 实现 `INSERT IGNORE` 或 `ON DUPLICATE KEY UPDATE`

---

## 十一、自定义与扩展

* **增加新 flag**：在正则 `(?P<flag>…)` 内加入枚举即可。
* **更多段落**：更新 `SECTION_MAP` 与 `iter_entries()` 中的段落检测逻辑。
* **时区感知**：替换 `datetime.combine` 为 `pendulum` 或 `pytz` 对象。
* **输出到其他数据库**：修改 `write_mysql()` 使用相应 SQLAlchemy URL。
