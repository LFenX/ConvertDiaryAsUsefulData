"""
diary_loader.py
---------------
从「清单式 Markdown 日记」读取 -> 解析 -> 写入 MySQL。

依赖：
    pip install pandas sqlalchemy pymysql python-dateutil
"""
#%%
from __future__ import annotations
import re
from pathlib import Path
from datetime import datetime, time, timedelta, date
from typing import Iterator, Dict, List
import pandas as pd
from sqlalchemy import create_engine
#%%
# ---------- 配置区 ----------
ROOT_DIR   = Path(r"C:\Users\LFen\Nutstore\1\NOTE\2025-07-14-PeriodOfSearchingPosition_DA\日记")
TABLE_NAME = "diary_entries"
MYSQL_URL  = "mysql+pymysql://LFen:20020419gR@127.0.0.1:3306/lfgran?charset=utf8mb4"
TIMEZONE   = "Asia/Singapore"              # 目前仅用于记录；如需真正时区感知可用 pendulum/pytz
# --------------------------------
# 段落标题（带反引号） -> 内部标识
SECTION_MAP = {
    "yesterday": "yesterday",
    "plan": "plan",
    "actual": "actual",
}
#%%
# 正则：hh:mm[-hh:mm] @cat : desc
PATTERN = re.compile(r"""
    ^\s*
    (?:\d+\.\s*)?                                   # 可选序号
    (?P<start>\d{1,2}:\d{2})                        # start
    (?:-(?P<end>\d{1,2}:\d{2}))?                    # 可选 end
    \s+
    `?@(?P<cat>[^\s:`]+)`?                      # @category（可反引号/多重/&）
    \s*[：:]\s*                                     # 英中冒号
    (?P<desc>.*?)                                   # 描述（非贪婪）
    (?:\s+                                          # ← 1+ 空白都行
      `?(?P<flag>done|pending|planned-OnTime|planned-WrongTime|extra)`?  # 可选 flag
    )?                                              # flag 整块可有可无
    \s*$
    """, re.VERBOSE)



#%%
# ----------------- 核心 -----------------
# 将 'hh:mm' 字符串转换为 time 对象
def to_time(hhmm: str) -> time:
    """'23:27' -> time(23,27)"""
    h, m = map(int, hhmm.split(":"))
    return time(h, m)

# ----------------- 解析函数 -----------------,返回 None 或 dict，对应于一条日记记录
def parse_line(
    line: str,
    section_key: str,
    file_date: date,
) -> Dict | None:
    m = PATTERN.match(line)
    if not m:
        return None

    start_t = to_time(m["start"])
    end_t   = to_time(m["end"] or m["start"])  # 单点事件: end == start


    # Anchor 日期
    if section_key == "yesterday":
        anchor = file_date - timedelta(days=1) if start_t >= time(12, 0) else file_date
    else:
        anchor = file_date

    start_dt = datetime.combine(anchor, start_t)
    end_dt   = datetime.combine(anchor, end_t)

    cats = [c.strip() for c in m["cat"].split("&") if c.strip()]
    category = ",".join(cats)  # 用逗号分隔写库
    flag = m["flag"]
    if end_dt < start_dt:
        end_dt += timedelta(days=1)

    duration = int((end_dt - start_dt).total_seconds() // 60) if end_dt!= start_dt else None

    return {
        "date": anchor,
        "segment": section_key,
        "start_dt": start_dt,
        "end_dt": end_dt,
        "duration": duration,
        "category": category,
        "activity_flag": flag,
        "description": m["desc"],
        "raw_line": line.strip(),
    }

# ----------------- 迭代器 ----------------- 用于逐行解析 Markdown 文件，返回记录字典
def iter_entries(md_path: Path) -> Iterator[Dict]:
    """逐行解析 markdown，yield 记录 dict"""
    file_date = datetime.strptime(md_path.stem, "%Y-%m-%d").date()

    current_section: str | None = None
    with md_path.open(encoding="utf-8") as f:
        massage=0
        for raw in f:
            line = raw.rstrip("\n")

            # 段落标题：``Yesterday`` / ``Plan`` / ``Actual``
            if line.startswith("`") and line.endswith("`"):
                label = line.strip("` ").lower()
                current_section = SECTION_MAP.get(label)
                continue

            if current_section is None or not line.strip():
                continue  # 未进入正文或空行

            rec = parse_line(line, current_section, file_date)
            if rec:
                massage += 1
                print(f'\r解析{massage}条记录',end='', flush=True)
                yield rec   # 返回解析后的记录字典，否则跳过
        print()

def load_day(target: date) -> pd.DataFrame:
    """解析指定日期（YYYY-MM-DD）的日记，返回 DataFrame"""
    month_dir = ROOT_DIR / target.strftime("%Y-%m")
    day_dir   = month_dir / target.strftime("%Y-%m-%d")
    md_path   = day_dir / f"{target:%Y-%m-%d}.md"

    if not md_path.exists():
        raise FileNotFoundError(md_path)

    records = list(iter_entries(md_path))
    if not records:
        raise ValueError(f"No parsable entries in {md_path}")

    df = pd.DataFrame(records)
    return df

def write_mysql(df: pd.DataFrame, if_exists: str = "append") -> None:
    """写入 MySQL；如需建表，可在 MySQL 用下列 DDL：
    CREATE TABLE diary_entries(
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        date DATE,
        segment ENUM('yesterday','plan','actual'),
        start_dt DATETIME,
        end_dt   DATETIME,
        duration INT,
        category VARCHAR(64),
        description TEXT,
        raw_line TEXT
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    print('正在写入 MySQL...')
    engine = create_engine(MYSQL_URL, echo=False, future=True)
    with engine.begin() as conn:
        df.to_sql(TABLE_NAME, conn, if_exists=if_exists, index=False, method="multi")
    print('写入完成')
# ----------------- CLI -----------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Parse diary markdown into MySQL")
    parser.add_argument(
        "--date",
        help="Target date, default today. Format YYYY-MM-DD",
        default=date.today().isoformat(),
    )
    args = parser.parse_args()

    target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    df = load_day(target_date)
    write_mysql(df)
    print(f"{len(df)} rows from {target_date} inserted into {TABLE_NAME}.")
