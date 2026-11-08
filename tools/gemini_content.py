# -*- coding: utf-8 -*-
"""Ask the user-selected Antigravity Gemini model to draft sourced wiki prose.

Drafts are stored under data/generated/, not in the mod tree. No tool access or
permission bypass is granted to the writing model.
"""
from pathlib import Path
import argparse
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent
AGY=Path.home()/"AppData/Local/agy/bin/agy.exe"

GUIDE_TOPICS={
"机制:战争基础": "战争基础：核心循环、敌人决策、单卡防御、复合性相阈值、枯竭、并行行动。",
"机制:盟友与招募": "盟友与招募：普通单位职能、具名人物个人委托、招募后随队、经验升级。",
"机制:伤口与治疗": "伤口与治疗：身体与精神损伤、状态变体、治疗、残疾和失败条件。",
"机制:补给与行军": "补给与行军：补给来源、治疗与队伍用途、路线牌组、不可逆地点、侦察区别。",
"机制:密传与飞升": "密传与飞升：刃密传升级、战斗收获、冷却、最终结局条件不只等于密传等级。",
"攻略:开局与资源": "开局与资源攻略：职能、储备、人物任务、人员轮换、战区离开前检查。",
"攻略:战斗准备": "战斗准备攻略：识别敌人阈值、整卡满足要求、特殊标签、失败代价与战后恢复。",
}

CHARACTER_TOPICS={
"食铁者": "sergei / sergei.first / friend.sergei / duel.sergei / defeated.sergei",
"大陆之敌": "camilla / camilla.first / friend.camilla / duel.camilla / duel.camilla.proterant",
"战争制造者": "wilhelm / wilhelm.first / friend.wilhelm / duel.wilhelm / duel.wilhelm.proterant",
"杜弗尔": "duffoure / duffoure.first；蔑世使徒中前任流亡者称其为不肖子。",
"前任流亡者": "三个 *.mentor 条目；模板 #PREVIOUSCHARACTERNAME# 是占位符，不是真实姓名。",
}


def call(prompt):
    if not AGY.exists():
        raise FileNotFoundError(f"Antigravity CLI not found: {AGY}")
    result=subprocess.run([str(AGY),"--model","gemini-3.8-flash-high","--sandbox",
                           "--disable-slash-commands",f"--print={prompt}"],
                          cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=240)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8",errors="replace"))
    return result.stdout.decode("utf-8",errors="replace").strip()+"\n"


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("kind",choices=["guides","characters","test"])
    ap.add_argument("--only",default="")
    args=ap.parse_args()
    if args.kind=="test":
        print(call("只回答：本地 Wiki 撰稿接口可用。"),end="")
        return
    outdir=ROOT/"data/generated"
    outdir.mkdir(parents=True,exist_ok=True)
    if args.kind=="guides":
        evidence=ROOT/"data/guide-source.txt"
        for title,topic in GUIDE_TOPICS.items():
            if args.only and args.only!=title: continue
            prompt=f'''你正在为一个本地的《密教模拟器》三刃使徒 Mod 中文 Wiki 撰写教程。请只根据“依据材料”写作，不得引入材料之外的具体数字、敌人、人物、流程或固定最优解。文字应清楚、温和、有节奏，适合第一次接触这套战争系统的读者；避免空话和营销腔。正文字数约 700—1100 字，使用 MediaWiki 维基文本，包含 3—5 个“== 小节 ==”标题，可用有序列表和要点，不使用 HTML 表格，不生成 wiki 链接。需要说明：行动条件因传承而异；alt 为满足条件的额外/替代分支、linked 为后续链。字段名保留 <code>英文</code>。若是“攻略”主题，请明确将策略建议与硬规则区分。不要输出评论或元说明。页面主题：{title}；重点：{topic}\n\n依据材料：\n{evidence.read_text(encoding="utf-8")}'''
            text=call(prompt)
            (outdir/(title+".wiki")).write_text(text,encoding="utf-8",newline="\n")
            print(f"{title}: {len(text)} chars",flush=True)
    else:
        source=ROOT/"data/shared-characters-source.json"
        for name,scope in CHARACTER_TOPICS.items():
            if args.only and args.only!=name: continue
            prompt=f'''你正在为一个本地的《密教模拟器》三刃使徒 Mod 中文 Wiki 撰写“跨 Mod 人物介绍”。仅根据提供的 JSON 中的人物原文与行动文本书写，不补充来源之外的生卒年、效忠对象、亲属关系、战役结果或隐秘身份。该人物在不同 Mod 中可能承担不同剧情角色，请区分这些角色，不强行组成未经证实的单一连续时间线。文字自然、克制，略带文学性但不做作。长度约 280—450 字，简体中文纯文本，1—2 段，不输出标题、链接或元说明。称谓采用原文中文。若资料只能支持其在某 Mod 出现，请明确写“在该传承中”等限定。人物：{name}；选取 ID：{scope}\n\n来源 JSON：\n{source.read_text(encoding="utf-8")}'''
            text=call(prompt)
            (outdir/(name+".txt")).write_text(text,encoding="utf-8",newline="\n")
            print(f"{name}: {len(text)} chars",flush=True)

if __name__=="__main__": main()
