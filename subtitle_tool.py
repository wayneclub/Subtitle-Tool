#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
Fix subtitles srt
"""
import argparse
import difflib
import os
import re
import subprocess
import sys
from pathlib import Path
import unicodedata
import pysubs2
from chardet import detect
from bs4 import BeautifulSoup
from opencc import OpenCC
import dictionary


SUBTITLE_FORMAT = ['.srt', '.ass', '.ssa', '.vtt', '.xml']
ARCHIVE_FORMAT = ['.7z,', '.gz', '.rar', '.tar', '.zip']


def get_encoding_type(source):
    """
    Get file encoding type
    """
    with open(source, 'rb') as source:
        rawdata = source.read()
    return detect(rawdata)['encoding']


def get_line_width(line):
    """
    Determines the width of the line in column positions.
    Args:
        line: A string, which may be a Unicode string.
    Returns:
        The width of the line in column positions, accounting for Unicode
        combining characters and wide characters.
    """
    if isinstance(line, str):
        width = 0
        for unicode in unicodedata.normalize('NFC', line):
            if unicodedata.east_asian_width(unicode) in ('W', 'F'):
                width += 2
            elif not unicodedata.combining(unicode):
                width += 1
        return width
    else:
        return len(line)

def replace_nth(s, sub, repl, n):
    """
    Replace nth
    """
    # where = [m.start() for m in re.finditer(sub, string)][n-1]
    # before = string[:where]
    # after = string[where:]
    # after = after.replace(sub, wanted, 1)
    # return before + after
    find = s.find(sub)
    # If find is not -1 we have found at least one match for the substring
    i = find != -1
    # loop util we find the nth or we find no match
    while find != -1 and i != n:
        # find + 1 means we start searching from after the last match
        find = s.find(sub, find + 1)
        i += 1
    # If i is equal to n we found nth match so replace
    if i == n:
        return s[:find] + repl + s[find+len(sub):]
    return s


def convert_utf8(srcfile):
    """
    Convert file to utf8
    """

    from_codec = get_encoding_type(srcfile)
    try:
        if from_codec.lower() != 'utf-8':
            print("\n將" + from_codec +
                  " 轉換成 UTF-8：\n---------------------------------------------------------------")
            if from_codec == 'BIG5' or from_codec == 'GB2312' or from_codec == 'GB2312':
                from_codec = 'CP950'

            with open(srcfile, 'r', encoding=from_codec) as input_src:
                data = input_src.read()
            with open(srcfile, 'w', encoding='UTF-8') as output_src:
                output_src.write(data)

    except UnicodeDecodeError:
        print('Decode Error')
    except UnicodeEncodeError:
        print('Encode Error')



def shift_subtitle(file_name, offset):
    """
    Shift subtitle
    """
    print('\n字幕平移：' + str(offset) + ' 秒\n')
    subs = pysubs2.load(file_name)
    subs.shift(s=offset)
    subs.save(file_name)


def merge_subtitle(first_file, second_file):
    """
    Merge subtitle
    """
    print('\n合併字幕：' + os.path.basename(first_file) + ' 和 ' + os.path.basename(second_file) +
          '\n---------------------------------------------------------------')
    subs_first = pysubs2.load(first_file)
    subs_second = pysubs2.load(second_file)
    delta = 5000
    offset = pysubs2.time.make_time(s=(subs_first[-1].end + delta)/1000)
    for sub in subs_second:
        subs_first.insert(-1, pysubs2.ssaevent.SSAEvent(start=sub.start +
                                                        offset, end=sub.end+offset, text=sub.text))

    new_file_name = first_file.replace('.srt', '-merge.srt')
    episode = re.search(r'(.+?S\d+E)(\d+)(.*?\.srt)', new_file_name)
    if episode:
        new_file_name = episode.group(
            1) + str(int((int(episode.group(2))+1)/2)).zfill(2) + episode.group(3)
    subs_first.save(new_file_name)
    print(os.path.basename(new_file_name) + '\t...合併完成\n')


def format_subtitle(file_name):
    """
    Format subtitle
    """
    subs = pysubs2.load(file_name)
    subs.save(file_name)


def translate_subtitle(file_name, is_simplified):
    """
    Uniform punctuation and translate term to Traditional Chinese
    """

    if is_simplified:
        Path(file_name).write_text(OpenCC('s2tw.json').convert(Path(file_name).read_text("utf8")), "utf8")

    subs = pysubs2.load(file_name)

    path = file_name.split(os.path.basename(file_name))[0]
    new_file_name = rename_subtitle(file_name)
    new_file_name = re.sub(r'(-|\.)ch[st]+', '', new_file_name, flags=re.I)
    new_file_name = re.sub(r'-AREA11', '', new_file_name)
    new_file_name = re.sub(
        r'(.+?)(\.)*[sS]([0-9]{2})[eE]([0-9]{2})(-E[0-9]{2})*.+',
        '\\1.S\\3E\\4\\5.srt',
        new_file_name)

    if '.zh' not in new_file_name:
        new_file_name = new_file_name.replace('.srt', '.zh.srt')

    print('\n' + new_file_name)
    print("\n訂正錯字、修改成台灣慣用語：\n---------------------------------------------------------------")

    original_line_num = len(subs)
    delete_list = []
    typo_compare_list = []

    for i, sub in enumerate(subs):
        text = sub.text.strip()

        if not text or text == '' or text == '\\n':
            delete_list.append(i)
            continue

        if sub.start == 0 and sub.end == 0:
            delete_list.append(i)
            continue

        if re.search(r'.*?字幕翻譯.*?', text):
            delete_list.append(i)
            continue

        if re.search(r'\{\\.*?(pos|fad)\([0-9\.]+,[0-9\.]+\).*?\}', text):
            text = '（' + re.sub(r'(\{.+?\})+', '', text) + '）'

        if re.search(r'\{.*?\\an8.*?\}', text):
            text = '{\\an8}' + re.sub(r'(\{.+?\})+', '', text)
        elif re.search(r'\{\\.+?\}', text):
            text = re.sub(r'(\{.+?\})+', '', text)

        if text == '我去':
            text = text.replace('我去', '')
            delete_list.append(i)
            continue

        text = re.sub(r',([\u4E00-\u9FFF]+)', ' \\1', text)
        text = re.sub(r'([\u4E00-\u9FFF]+),', '\\1', text)

        text = re.sub(r'([\u4E00-\u9FFF]+)\[', '\\1 [', text)
        text = re.sub(r'\]([\u4E00-\u9FFF]+)', '] \\1', text)

        # Uniform and fix punctuation errors
        if re.search(r'[\u4E00-\u9FFF]+', text):
            text = text.replace('＂', '"')
            text = text.replace('➚', '')
            text = text.replace('…', '…')
            text = text.replace('..', '…')
            text = text.replace('．．．', '…')
            text = text.replace('﹒﹒﹒', '…')
            text = text.replace('。。。', '…')
            text = text.replace(' …', '…')
            text = text.replace('….', '…')
            text = text.replace('!?', '⁉︎ ')
            text = text.replace('?!', '⁉︎ ')
            text = text.replace('!', '！')
            text = text.replace('?', '？')
            text = text.replace(' ！', '！')
            text = text.replace(' ？', '？')
            text = text.replace('！？', '⁉︎ ')
            text = text.replace('？!', '⁉︎ ')
            text = text.replace('！', '！ ')
            text = text.replace('？', '？ ')
            text = text.replace('？ ？', '？？')
            text = text.replace('！ ！', '！！')
            text = text.replace('，', ' ')
            text = text.replace('。', ' ')
            text = text.replace('、 ', '、')
            text = text.replace(' 、', '、')
            text = text.replace(',\\n\\r', '')
            text = text.replace(':', '：')
            text = text.replace('： ', '：')
            text = text.replace('：\\n', '：')
            text = text.replace('~', '～')
            text = text.replace('|', '｜')
            text = text.replace(' |', '｜')
            text = text.replace('| ', '｜')
            text = re.sub(r'([\u4E00-\u9FFF]+)\.', '\\1 ', text)
            text = text.replace('(', '（')
            text = text.replace('（-=', '（')
            text = text.replace('（-= ', '（')
            text = text.replace('-=', '（')
            text = text.replace('-= ', '（')
            text = text.replace(' （', '（')
            text = text.replace('（ ', '（')
            text = text.replace('（\\n\\r', '（')
            text = text.replace(')', '）')
            text = text.replace('=-）', '）')
            text = text.replace(' =-）', '）')
            text = text.replace('=-', '）')
            text = text.replace(' =-', '）')
            text = text.replace(' ）', '）')
            text = text.replace('\\n\\r)', '）')
            text = text.replace(r'\h', '')
            text = text.replace('•', '・')
            text = text.replace('‧', '・')
            text = text.replace('·', '・')
            text = text.replace('．', '・')
            text = text.replace('〝', '「')
            text = text.replace('〞', '」')
            text = text.replace('『', '「')
            text = text.replace('』', '」')
            text = text.replace('「 ', '「')
            text = text.replace(' 」', '」')
            text = text.replace('注：', '註：')
            text = text.replace('（註：', '\\n（註：')
            text = text.replace('-（', '（')
            text = text.replace('->', ' → ')
            text = text.replace('<-', ' ← ')
            text = re.sub(r'^[<＜]', '〈', text)
            text = re.sub(r'[>＞]$', '〉', text)
            text = text.replace('）\\n-', '）\\n')
            text = text.replace('- ', '-')
            text = text.replace('　', ' ')

        text = text.replace('“', '"')
        text = text.replace('”', '"')
        text = text.replace('’', "'")
        text = text.replace('‘', "'")

        text = '\\n'.join(filter(None, text.split('\\n')))

        text = re.sub(r'([A|P]M)([0-9]{2})：([0-9]{2})', '\\2:\\3 \\1 ', text)
        text = re.sub(r'([A|P]M) ([0-9]{2})：([0-9]{2})', '\\2:\\3 \\1 ', text)
        text = re.sub(r'([0-9]+)：([0-9]+)：([0-9]+)', '\\1:\\2:\\3', text)
        text = re.sub(r'([0-9]+)：([0-9]+)', '\\1:\\2', text)

        if '-' not in text:
            if len(re.findall(r'^[\u4E00-\u9FFF]\\n', text)) > 2 \
                    or len(re.findall(r'（[\u4E00-\u9FFF]\\n', text)) > 2:
                text = text.replace('\\n', '')

        text = re.sub(
            r'([\u4E00-\u9FFF]+)…([\u4E00-\u9FFF]+)', '\\1… \\2', text)

        text = re.sub(r'([\u4E00-\u9FFF])\.', '\\1 ', text)

        text = re.sub(r'\"(.*?[\u4E00-\u9FFF]+.*?)\"', '「\\1」', text)
        text = re.sub(r'\'(.*?[\u4E00-\u9FFF]+.*?)\'', '「\\1」', text)
        text = text.replace(' 」', '」')

        # 刪掉多餘'"
        text = re.sub(r'^[\"\'](.*?[\u4E00-\u9FFF]+)', '\\1', text)
        text = re.sub(r'([\u4E00-\u9FFF]+)[\"\']$', '\\1', text)


        text = re.sub(r'([0-9]+)\.([\u4E00-\u9FFF]+)', '\\1. \\2', text)

        episode = re.search(r'（第(.*?)[集|話|回](.*?)）(.*)', text)
        if episode:
            text = '（第' + dictionary.translate(episode.group(1), dictionary.NUMBER).strip() + \
                '集' + episode.group(2) + '）' + episode.group(3)

        episode = re.search(r'^第(.*?)[集|話|回]$', text)
        if episode:
            text = '（第' + \
                dictionary.translate(episode.group(
                    1), dictionary.NUMBER).strip() + '集）'

        if text == '下集預告':
            text = '（下集預告）'

        if text == '=下集預告=':
            text = '（下集預告）'

        if text == '下 集 預 告':
            text = '（下集預告）'

        if text == '前情提要':
            text = '（前情提要）'

        if text == '前 情 提 要':
            text = '（前情提要）'

        if text == '本集回顧':
            text = '（本集回顧）'

        if text == '本 集 回 顧':
            text = '（本集回顧）'

        conversation = re.search(r'(\\t| )-[ \u4E00-\u9FFF]+', text)
        if conversation:
            text = text.replace(' -', '\\n-')
            text = text.replace('\\t-', '\\n-')
            text = ' '.join(text.split())

        text = re.sub(r'(^[\u4E00-\u9FFF]+)\\n-', '-\\1\\n-', text)

        text = text.replace('\\n\\n', '\\n')
        text = text.replace('  ', ' ')
        text = text.replace(' 　　', ' ')

        original_text = text

        # 將大陸、香港用語轉為臺灣用語
        text = dictionary.translate(text, dictionary.CONTEXT)

        # 修正錯別字
        text = dictionary.translate(text, dictionary.TYPO)

        subs[i].text = text

        # 錯字比較
        if original_text != text:
            typo_compare = {}
            typo_compare['start'] = sub.start
            typo_compare['end'] = sub.end
            typo_compare['original_text'] = original_text
            typo_compare['new_text'] = text
            typo_compare_list.append(typo_compare)

    for i in reversed(delete_list):
        del subs[i]

    delete_list = []
    for i, sub in enumerate(subs):
        text = sub.text

        if i > 0 and sub.start == subs[i-1].start and sub.end == subs[i-1].end:
            if text.replace('（', '').replace('）', '') \
                    == subs[i-1].text.replace('（', '').replace('）', ''):

                if subs[i-1].text[0] == '（':
                    delete_list.append(i)
                else:
                    delete_list.append(i-1)

            else:
                if text[0] == '（':
                    if subs[i-1].text[0] == '（':
                        if "）\\n" in subs[i-1].text:
                            match = list(re.finditer(r'）\\n', subs[i-1].text))
                            pos = match[-1].span()[1]
                            if match:
                                subs[i-1].text = subs[i-1].text[:pos] + \
                                    text + '\\n' + subs[i-1].text[pos:]
                        else:
                            subs[i-1].text = subs[i-1].text + '\\n' + text
                    else:
                        subs[i-1].text = text + '\\n' + subs[i-1].text
                else:
                    subs[i-1].text = subs[i-1].text + '\\n' + text
                delete_list.append(i)
        else:
            subs[i].text = text

    for i in reversed(delete_list):
        del subs[i]

    subs.sort()

    overlap_num = 0
    overlap_list = []

    for i, sub in enumerate(subs):
        text = sub.text
        text = text.replace('）\\n（', '\\n')
        if re.search(r'（註：.+?）\\n', text, flags=re.S):
            tmp = text.split('）\\n')
            text = tmp[1] + '\\n' + tmp[0] + '）'
        text = text.replace('  ', ' ')
        subs[i].text = text

        illegal_character = re.findall(
            r'[^αa-zA-Z0-9\u4E00-\u9FFF!?\[\]\{\}&/\\,\.;:\(\)%$><=\'\"~\+\-\* （），。、——＋！×？⁉︎：・…「」／→←〈〉《》＞＜～％｜♥★♪＆©\n]', text)
        if len(illegal_character) > 0:
            print('非法字源：\n' + str(i+1) + '\n' + pysubs2.subrip.SubripFormat.ms_to_timestamp(sub.start) +
                  ' --> ' + pysubs2.subrip.SubripFormat.ms_to_timestamp(sub.end) + '\n' +
                  text.replace('\\n', '\n') + '\n\n')
            print(illegal_character)


        subs[i].text = fix_overlength(text)


        if i > 0:
            if sub.start < subs[i-1].start or sub.end < subs[i-1].end or sub.start < subs[i-1].end:
                overlap_num += 1
                overlap_list.append(i)

        for typo_compare in typo_compare_list:
            if typo_compare['start'] == sub.start and typo_compare['end'] == sub.end:
                typo_compare.update({'index': i + 1})

    # 字幕重疊
    if overlap_num > 0:
        overlap_file = open(
            path + new_file_name.replace('.srt', '-字幕重疊.txt'), 'w', encoding='utf-8')
        for index in overlap_list:
            text = subs[index].text
            overlap_file.write(str(index) + '\n' + pysubs2.subrip.SubripFormat.ms_to_timestamp(subs[index].start) +
                               ' --> ' + pysubs2.subrip.SubripFormat.ms_to_timestamp(subs[index].end) + '\n' +
                               text.replace('\\N', '\n') + '\n\n')

    subs.save(path + new_file_name)

    if path + new_file_name != file_name:
        os.remove(file_name)

    print('{0: <15}'.format("原始行數：" + str(original_line_num)) +
          '{0: <15}'.format("修正後行數：" + str(len(subs))) +
          '{0: <15}'.format("重疊行數：" + str(overlap_num)) + '\n')

    # 錯字比較
    print_typo_compare(path + new_file_name.replace('.srt', '-修正錯字.txt'), typo_compare_list)

def fix_overlength(text):
    """ 修正過長字幕 """
    lines = text.split('\\N')
    text = ''
    for single_line in lines:
        if get_line_width(single_line.replace('{\\an8}', '')) > 41:
            chunks = single_line.split(' ')
            str_len = 0
            size = []
            for piece in chunks:
                size.append(get_line_width(piece.replace('{\\an8}', '')))

            count = 0
            new_line = []
            for i, tmp in enumerate(size):
                if count+tmp <= 40:
                    count += tmp
                else:
                    new_line.append(i)
                    count = tmp

            single_line = ''
            for x, piece in enumerate(chunks):
                if x in new_line:
                    single_line += '\n' + piece
                else:
                    if x==0:
                        single_line += piece
                    else:
                        single_line += ' ' + piece

            text += single_line + '\n'
        else:
            text += single_line + '\n'

    return text.strip()

def print_overlap(file_name, overlap_list):
    """ 印出重疊字幕 """
    if len(overlap_list) == 0:
        sys.exit()

    # overlap_file = open(file_name.replace('.srt', '-字幕重疊.txt'), 'w')
    # for index in overlap_list:
    #     text = subs[index].text
    #     overlap_file.write(str(index) + '\n' + pysubs2.subrip.SubripFormat.ms_to_timestamp(subs[index].start) +
    #                         ' --> ' + pysubs2.subrip.SubripFormat.ms_to_timestamp(subs[index].end) + '\n' +
    #                         text.replace('\\N', '\n') + '\n\n')

def print_overlength(file_name, overlength_list):
    """ 印出過長字幕 """
    if len(overlength_list) == 0:
        sys.exit()

def print_typo_compare(file_name, typo_compare_list):
    """ 印出錯字 """
    if len(typo_compare_list) == 0:
        sys.exit()

    typo_compare_file = open(file_name, 'w', encoding='utf-8')
    for typo_compare in typo_compare_list:
        typo_compare_file.write(str(typo_compare['index']) + '\n')

        typo_compare_file.write(pysubs2.subrip.SubripFormat.ms_to_timestamp(
            typo_compare['start']) + ' --> ' + pysubs2.subrip.SubripFormat.ms_to_timestamp(typo_compare['end']) + '\n')

        original_text = ''
        new_text = ''

        for i, s in enumerate(difflib.ndiff(typo_compare['original_text'].replace('\\N', '\n'), typo_compare['new_text'].replace('\\N', '\n'))):

            if s[0] == ' ':
                original_text += s[2:]
                new_text += s[2:]
            elif s[0] == '-':
                original_text += '【' + s[-1] + '】'
            elif s[0] == '+':
                new_text += '【' + s[-1] + '】'

        original = original_text.split('\n')
        new = new_text.split('\n')

        for i, (a, b) in enumerate(zip(original, new)):
            offset = str(40 - get_line_width(a))
            if int(offset) <= 0:
                offset = 10

            if len(original) > 1:
                if i == 0:
                    typo_compare_file.write(
                        f'{a:{offset}} ' + '\t---->\t' + b + '\n')
                else:
                    typo_compare_file.write(
                        f'{a:{offset}} ' + '\t     \t' + b + '\n')
            else:
                typo_compare_file.write(
                    f'{a:{offset}} ' + '\t---->\t' + b + '\n')

        typo_compare_file.write('\n')


def convert_subtitle(original_file):
    """Convert subtitle extension"""
    extension = Path(original_file).suffix

    if extension != '.srt':
        print("\n將" + extension +
              " 轉換成.srt：\n---------------------------------------------------------------")
        if extension == '.ssa' or extension == '.ass':
            file_name = ass_to_srt(original_file)
        elif extension == '.vtt':
            file_name = vtt_to_srt(original_file)
            print(file_name)
        elif extension == '.xml':
            file_name = xml_to_srt(original_file)
    else:
        file_name = original_file

    return file_name


def rename_subtitle(original_file_name):
    """Rename subtitle"""
    new_file_name = os.path.basename(original_file_name)
    new_file_name = new_file_name.replace(".ass", ".srt")
    new_file_name = new_file_name.replace(".ssa", ".srt")
    new_file_name = new_file_name.replace(".vtt", ".srt")
    new_file_name = new_file_name.replace(".xml", ".srt")
    new_file_name = new_file_name.replace('.rar', '')
    new_file_name = new_file_name.replace('.zip', '')
    new_file_name = new_file_name.replace('WEBRip', 'WEB-DL')
    return new_file_name


def convert_ass_content(file_contents, ass_type: str):
    """Convert content of vtt file to str format"""

    replacement = re.sub(r"\{\\c\&[A-Z0-9]+\&\}", "", file_contents)

    if ass_type == '.ssa':
        replacement = re.sub(r"&H[A-Z0-9]{6,8}", "0", replacement)

    replacement = re.sub(
        r",[cC]aption.*?,.*?,[0]+,[0]+,[0]+,.*?,(\{.+?\})*(.+)", r",Caption,,0000,0000,0000,,（\2）", replacement)
    replacement = re.sub(
        r",[cC]omment.*?,.*?,[0]+,[0]+,[0]+,.*?,(\{.+?\})*(.+)", r",Comment,,0000,0000,0000,,（\2）", replacement)
    replacement = re.sub(
        r",[nN]ote.*?,.*?,[0]+,[0]+,[0]+,.*?,(\{.+?\})*(.+)", r",Note,,0000,0000,0000,,（\2）", replacement)
    replacement = re.sub(
        r",註釋,.*?,[0]+,[0]+,[0]+,.*?,(\{.+?\})*(.+)", r",註釋,,0000,0000,0000,,（\2）", replacement)
    replacement = re.sub(
        r",[cC]hat.*?,.*?,[0]+,[0]+,[0]+,.*?,(\{.+?\})*(.+)", r",Chat,,0000,0000,0000,,（\2）", replacement)
    replacement = re.sub(
        r",[lL]yrics.*?,.*?,[0]+,[0]+,[0]+,.*?,(\{.+?\})*(.+)", r",Lyrics,,0000,0000,0000,,{\\an8}\2", replacement)
    replacement = re.sub(
        r",歌詞.*?,.*?,[0]+,[0]+,[0]+,.*?,(\{.+?\})*(.+)", r",Lyrics,,0000,0000,0000,,{\\an8}\2", replacement)
    replacement = re.sub(
        r",[sS]ong.*?,.*?,[0]+,[0]+,[0]+,.*?,(\{.+?\})*(.+)", r",Song,,0000,0000,0000,,{\\an8}\2", replacement)

    return replacement


def convert_vtt_content(file_contents):
    """Convert content of vtt file to str format"""

    # 修正前5分鐘內Netflix字幕顯示在上方
    # replacement = re.sub(
    #     r"(00:0[0-4]:\d\d).(\d\d\d) --> (\d\d:\d\d:\d\d).(\d\d\d).*?(line:[1]*[0-9](\.[0-9]{2})*%).*?\n(.+?（)", r"\1,\2 --> \3,\4\n{\\an8}\7", file_contents)
    # replacement = re.sub(
    #     r"(00:0[0-4]:\d\d).(\d\d\d) --> (\d\d:\d\d:\d\d).(\d\d\d).*?(line:[1]*[0-9](\.[0-9]{2})*%).*?\n", r"\1,\2 --> \3,\4\n", replacement)

    # 字幕顯示在上方
    replacement = re.sub(
        r"(\d\d:\d\d:\d\d).(\d\d\d) --> (\d\d:\d\d:\d\d).(\d\d\d).*?(line:[1]*[0-9](\.[0-9]{2})*%).*?\n(.+?（)", r"\1,\2 --> \3,\4\n{\\an8}\7", file_contents)

    replacement = re.sub(
        r"(\d\d:\d\d:\d\d).(\d\d\d) --> (\d\d:\d\d:\d\d).(\d\d\d)(.+)*\n", r"\1,\2 --> \3,\4\n", replacement)
    replacement = re.sub(
        r"(\d\d:\d\d).(\d\d\d) --> (\d\d:\d\d).(\d\d\d)(.+)*\n", r"\1,\2 --> \3,\4\n", replacement)
    replacement = re.sub(
        r"(\d\d).(\d\d\d) --> (\d\d).(\d\d\d)(.+)*\n", r"\1,\2 --> \3,\4\n", replacement)
    replacement = re.sub(r"WEBVTT.*?\n", "", replacement)
    replacement = re.sub(r"NOTE Netflix\n", "", replacement)
    replacement = re.sub(r"NOTE Profile:.+\n", "", replacement)
    replacement = re.sub(r"NOTE Date:.+\n", "", replacement)
    replacement = re.sub(r"NOTE Segment.+\n", "", replacement)
    replacement = re.sub(r"NOTE \/Segment.+\n", "", replacement)
    replacement = re.sub(r"Kind:[ \-\w]+\n", "", replacement)
    replacement = re.sub(r"Language:[ \-\w]+\n", "", replacement)
    replacement = re.sub(r"&lrm;", "", replacement)
    replacement = re.sub(
        r"(<[^>]+>)*<[^>]+>(.*?)<\/[^>]+>(<\/[^>]+>)*", r"\2", replacement)
    replacement = re.sub(r"<\d\d:\d\d:\d\d.\d\d\d>", "", replacement)
    replacement = re.sub(r"<\\[^>]+>", "", replacement)
    replacement = re.sub(
        r"::[\-\w]+\([\-.\w\d]+\)[]*{[.,:;\(\) \-\w\d]+\n }\n", "", replacement)
    replacement = re.sub(r"Style:\n##\n", "", replacement)
    replacement = re.sub(r"(-.+?) (-.+)", r"\1\n\2", replacement)
    replacement = re.sub(r'[\t]*\n{3,}', '', replacement, re.MULTILINE)
    return replacement


def convert_xml_content(file_contents):
    """Convert xml content"""
    subs = []
    soup = BeautifulSoup(file_contents, 'xml')
    for section in soup.findAll('dia'):
        start_time = int(section.find('st').getText())
        end_time = int(section.find('et').getText())
        text = section.find('sub').getText()
        if text[0] == '[':
            text = text.replace('[', '（', 1)
        if text[-1] == ']':
            text = text[:-1] + '）'

        text = text.replace('， ', '，')

        position = section.find('position')['vertical-margin']
        if position and int(position.strip('%')) < 20:
            text = '{\\an8}' + text

        subs.append(pysubs2.ssaevent.SSAEvent(start_time, end_time, text))

    return subs


def file_create(str_name_file, str_data):
    """Create a file with some data"""
    with open(str_name_file, 'w', encoding='utf-8') as f:
        f.writelines(str(str_data))


def read_text_file(str_name_file):
    """Read a file text"""
    with open(str_name_file, 'r', encoding='utf-8') as f:
        return f.read()


def ass_to_srt(str_name_file):
    """Convert vtt file to a srt file"""
    file_contents: str = read_text_file(str_name_file)
    str_data: str = ""
    if Path(str_name_file).suffix == '.ssa':
        str_data = str_data + convert_ass_content(file_contents, '.ssa')
    else:
        str_data = str_data + convert_ass_content(file_contents, '.ass')
    os.remove(str_name_file)
    str_name_file: str = str(Path(
        str_name_file).parent) + '/' + rename_subtitle(str_name_file)
    file_create(str_name_file, str_data)
    format_subtitle(str_name_file)
    print(os.path.basename(str_name_file) + "\t...轉檔完成")

    return str_name_file


def vtt_to_srt(str_name_file):
    """Convert vtt file to a srt file"""
    file_contents: str = read_text_file(str_name_file)
    str_data: str = ""
    str_data = str_data + convert_vtt_content(file_contents)
    os.remove(str_name_file)
    str_name_file: str = str(Path(
        str_name_file).parent) + '/' + rename_subtitle(str_name_file)
    file_create(str_name_file, str_data)
    format_subtitle(str_name_file)
    print(os.path.basename(str_name_file) + "\t...轉檔完成")

    return str_name_file


def xml_to_srt(str_name_file):
    """xml_to_srt"""
    file_contents: str = read_text_file(str_name_file)
    str_data: str = ""
    subs = convert_xml_content(file_contents)
    os.remove(str_name_file)
    str_name_file: str = str(Path(
        str_name_file).parent) + '/' + rename_subtitle(str_name_file)
    # subs.save(str_name_file)
    print(os.path.basename(str_name_file) + "\t...轉檔完成")

    return str_name_file


def archive_subtitle(path, platform):
    """
    Archive subtitles
    """
    platforms = [{'id': 'nf', 'name': 'Netflix'},
                 {'id': 'kktv', 'name': 'KKTV'},
                 {'id': 'linetv', 'name': 'LineTV'},
                 {'id': 'friday', 'name': 'friDay'}]

    platform = next(item for item in platforms if item['id'] == platform)['name']

    print("\n將srt封裝打包：\n---------------------------------------------------------------")
    zipname = path.replace(' ', '\\ ') + '.WEB-DL.' + \
        platform + '.zh-Hant.zip '
    print(zipname)
    os.system('python3 -m zipfile -c ' + zipname +
              path.replace(' ', '\\ ') + '/*.srt')


def walk_dir(top_most_path, args):
    """
    Walk a directory
    """

    for f in os.listdir(top_most_path):
        pathname = os.path.join(top_most_path, f)
        if Path(pathname).suffix in SUBTITLE_FORMAT:
            handle_subtitle(args, pathname)

    if args.zip:
        archive_subtitle(top_most_path, args.zip)


def handle_subtitle(args, subtitle):
    """Handle subtitle"""
    if not os.path.exists(subtitle):
        print(subtitle + " 檔案不存在\n")
        sys.exit()

    convert_utf8(subtitle)

    if args.format:
        format_subtitle(subtitle)
    elif args.convert:
        convert_subtitle(subtitle)
    elif args.shift:
        offset = float(args.shift)
        shift_subtitle(subtitle, offset)
    elif args.merge:
        second_subtitle = args.merge
        if Path(second_subtitle).suffix == '.srt':
            merge_subtitle(subtitle, second_subtitle)
    elif args.translate == 's':
        translate_subtitle(convert_subtitle(subtitle), True)
    elif args.translate != 's':
        translate_subtitle(convert_subtitle(subtitle), False)

def main():
    """
    Main function
    """
    parser = argparse.ArgumentParser(
        description='字幕處理')
    parser.add_argument('path',
                        help='欲修改字幕檔案的位置')
    parser.add_argument('-t',
                        '--translate',
                        dest='translate',
                        nargs='?',
                        const=True,
                        help='錯字修正')
    parser.add_argument('-c',
                        '--convert',
                        dest='convert',
                        nargs='?',
                        const=True,
                        help='字幕轉成srt檔')
    parser.add_argument('-f',
                        '--format',
                        dest='format',
                        nargs='?',
                        const=True,
                        help='排列整理字幕')
    parser.add_argument('-s',
                        '--shift',
                        dest='shift',
                        help='平移字幕')
    parser.add_argument('-m',
                        '--merge',
                        dest='merge',
                        help='合併字幕')
    parser.add_argument('-z',
                        '--zip',
                        dest='zip',
                        help='打包字幕')

    args = parser.parse_args()

    path = args.path
    if os.path.isdir(path):
        walk_dir(path, args)
    else:
        if Path(path).suffix in ARCHIVE_FORMAT:
            extract_command = 'unar \'' + path + '\' -o ' + str(Path(path).parent)
            result = re.search(r'Successfully extracted to "(.+?)"', subprocess.getoutput(extract_command))
            if result:
                output_path = result.group(1)
                if os.path.isdir(output_path):
                    walk_dir(output_path, args)
                else:
                    handle_subtitle(args, output_path)
        elif Path(path).suffix in SUBTITLE_FORMAT:
            handle_subtitle(args, path)
        else:
            print(os.path.basename(path) + " 非字幕檔\n")


if __name__ == "__main__":
    main()
    # print(get_line_width('美國 MMR Resorts 主導開發'))
