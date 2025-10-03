#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mozc_to_rime_filter_jp.py
将 Mozc dictionary00~09 合并并转换为 Rime 的 .dict.yaml
功能：
 - 保留所有含有日语字符（假名 / 汉字）的词条
 - 跳过纯英文、纯数字、符号等非日语词条
 - skipped.tsv: 无法生成 romaji 的词条
"""
import os
import glob
import re
import argparse
from datetime import datetime
import jaconv

# 可选 pykakasi
try:
    from pykakasi import kakasi
    _k = kakasi()
    def pykakasi_convert(text: str) -> str:
        return "".join([item["hepburn"] for item in _k.convert(text)])
    HAS_PYKAKASI = True
except Exception:
    HAS_PYKAKASI = False
    pykakasi_convert = None

ASCII_RE = re.compile(r'^[a-z0-9]+$')
JP_CHAR_RE = re.compile(r'[\u3040-\u30FF\u4E00-\u9FFF]')  # 假名或汉字

def is_ascii_romaji(s: str) -> bool:
    return bool(ASCII_RE.fullmatch(s))

def has_japanese(word: str) -> bool:
    return JP_CHAR_RE.search(word) is not None

def convert_reading_to_romaji(reading: str) -> str:
    if not reading:
        return ""
    r_kata = jaconv.hira2kata(reading).replace('\u3094', '\u30F4')
    romaji = jaconv.kana2alphabet(r_kata).lower()
    romaji = re.sub(r'\s+', '', romaji)
    romaji_clean = re.sub(r'[^a-z0-9]', '', romaji)

    if is_ascii_romaji(romaji_clean):
        return romaji_clean

    if HAS_PYKAKASI and pykakasi_convert:
        try:
            r_py = pykakasi_convert(r_kata)
            r_py = re.sub(r'\s+', '', r_py).lower()
            r_py_clean = re.sub(r'[^a-z0-9]', '', r_py)
            if r_py_clean:
                return r_py_clean
        except Exception:
            pass

    return romaji_clean

def mozc_to_rime(mozc_dir: str, pattern: str, dict_name: str, output_file: str):
    files = sorted(glob.glob(os.path.join(mozc_dir, pattern)))
    if not files:
        raise FileNotFoundError(f"未找到符合模式的文件：{os.path.join(mozc_dir, pattern)}")

    results = []
    skipped = []
    stats = {"processed_lines": 0, "converted": 0, "skipped": 0, "filtered_nonjp": 0}

    for fp in files:
        with open(fp, "r", encoding="utf-8", errors="ignore") as fin:
            for line in fin:
                stats["processed_lines"] += 1
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                reading = parts[0].strip()
                word = parts[4].strip()
                if not word:
                    continue

                # 过滤掉不含日语的词条
                if not has_japanese(word):
                    stats["filtered_nonjp"] += 1
                    continue

                romaji = convert_reading_to_romaji(reading)
                if not romaji:
                    stats["skipped"] += 1
                    skipped.append((word, reading, "无法生成ASCII romaji"))
                    continue

                results.append((word, romaji))
                stats["converted"] += 1

    today = datetime.today().strftime("%Y.%m.%d")
    header = (
        "# Rime dictionary converted from Mozc\n"
        "# encoding: utf-8\n"
        f"---\nname: {dict_name}\nversion: \"{today}\"\nsort: by_weight\ncolumns:\n  - text\n  - code\n...\n\n"
    )

    with open(output_file, "w", encoding="utf-8") as fout:
        fout.write(header)
        for word, romaji in results:
            fout.write(f"{word}\t{romaji}\n")

    with open("skipped.tsv", "w", encoding="utf-8") as fskip:
        for word, reading, reason in skipped:
            fskip.write(f"{word}\t{reading}\t{reason}\n")

    return stats, len(results), "skipped.tsv"

def main():
    p = argparse.ArgumentParser(description="Convert Mozc dictionary files to Rime .dict.yaml (filter non-Japanese words).")
    p.add_argument("--mozc-dir", default="./mozc-dict", help="存放mozc字典文件的目录")
    p.add_argument("--pattern", default="dictionary[0-9][0-9].txt", help="glob 模式匹配 mozc 文件")
    p.add_argument("--name", default="mozc_jp", help="输出词典的 name")
    p.add_argument("--out", default=None, help="指定输出文件")
    args = p.parse_args()

    out_file = args.out or f"{args.name}.dict.yaml"
    stats, total, skipped_file = mozc_to_rime(args.mozc_dir, args.pattern, args.name, out_file)

    print("转换完成。")
    print("输出文件：", out_file)
    print(f"共处理行数：{stats['processed_lines']}")
    print(f"成功转换：{stats['converted']} 条")
    print(f"写入总条目：{total}")
    print(f"跳过（无 romaji）：{stats['skipped']}，已写入 {skipped_file}")
    print(f"过滤非日语词条：{stats['filtered_nonjp']}")
    if not HAS_PYKAKASI:
        print("提示：未检测到 pykakasi（可选），安装后可提高转换准确性：pip install pykakasi")

if __name__ == "__main__":
    main()
