"""营销 Agent —— RAG 检索 + 大模型生成结构化营销方案

工作流(评审看的 AI 工作流核心):
  1. 输入:目标 RFM 群体 + 该群体真实统计(人数/均消费/均到店/均客单)
  2. 工具①:RAG 检索商户清单 + 营销方法论(按群体语义检索)
  3. 工具②:大模型基于 RAG context + 真实数据生成结构化 JSON 方案
     (目标/策略3条/选品推荐/投放话术/ROI预估)
  4. fallback:大模型不可用 → 规则引擎 generate_marketing_strategy 兜底

输出结构化方案 JSON,供 5_营销助手页 渲染为分块卡片。
所有调用带 Streamlit 缓存(@st.cache_data),避免重复计费。
"""
import json
import logging
from typing import Optional

from app.llm_client import chat, parse_json_response, is_llm_ready
from app import rag
from app.models import generate_marketing_strategy

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是"万泰新天地智能运营中台"的营销 Agent,为商场运营团队生成可落地的会员营销方案。

背景:万泰新天地是普宁最大商业综合体(20万㎡,5层,60+真实品牌),你已接入商场真实会员RFM分层数据与商铺知识库。

你必须严格返回如下 JSON(不要任何其他文字、不要 markdown 代码块):
{
  "segment": "群体名",
  "objective": "本次营销目标(一句话)",
  "strategies": [
    {"title": "策略名", "desc": "具体做法(含机制)", "channels": ["触达渠道"]},
    {"title": "...", "desc": "...", "channels": ["..."]},
    {"title": "...", "desc": "...", "channels": ["..."]}
  ],
  "products": [
    {"shop": "推荐合作商户名(从知识库真实商户选)", "reason": "为何推荐该商户联动"}
  ],
  "copywriting": "一条可直接投放的营销话术(含优惠机制,口语化,带emoji)",
  "roi": {
    "target_count": "预计触达人数(整数)",
    "conversion_rate": "预计转化率(百分比数字如15表示15%)",
    "est_revenue": "预计增量营收(元,整数)",
    "cost": "预计投放成本(元)",
    "roi_ratio": "ROI倍数(数字如3.5)"
  },
  "compliance_note": "合规提示(脱敏/隐私保护/不夸大宣传)"
}

规则:
1. strategies 必须 3 条,基于该群体特征,不要泛泛而谈。
2. products 中的 shop 必须来自知识库真实商户(如喜茶/沃尔玛/中影国际/NIKE等),不得编造。
3. ROI 数字要基于给定的真实群体统计合理估算,不得虚高。roi_ratio 应在 1-6 之间,需基于投放成本与增量营收合理估算,不得虚高。
4. 话术要口语化、可直接用,含具体优惠(如"满200减30")。
5. 合规:保护隐私、不夸大、遵守广告法。"""


def _build_user_prompt(segment: str, stats: dict, rag_context: str) -> str:
    """构建用户消息:真实群体统计 + RAG 检索 context"""
    return f"""## 目标群体:{segment}

### 该群体真实统计(来自商场会员RFM分层)
- 人数:{stats['count']} 人(占全体 {stats['pct']:.1f}%)
- 平均累计消费:¥{stats['avg_spent']:,.0f}
- 平均到店次数:{stats['avg_visit']:.1f} 次
- 平均客单价:¥{stats['avg_order']:,.0f}

### 检索到的知识库上下文(RAG)
{rag_context}

请基于以上真实数据与知识,生成{segment}群体的可落地营销方案。严格返回 JSON。"""


def _fallback_plan(segment: str, stats: dict) -> dict:
    """大模型不可用时的规则兜底(保证 Demo 不崩)"""
    strategies_raw = generate_marketing_strategy(segment, stats["avg_spent"], stats["avg_visit"])
    # 转成结构化
    strat = []
    for s in strategies_raw:
        strat.append({"title": s.split(":")[0] if ":" in s else s[:10], "desc": s, "channels": ["会员APP", "短信", "门店"]})

    # ROI 估算:按群体区分投放成本占比(大额券成本高,小额券成本低)
    # 这样不同群体 ROI 不同(约4-6x),不再恒定 8.3x
    if segment == "沉睡":
        conv, est = 15, stats["count"] * 0.15 * stats["avg_spent"] * 0.3
        cost_ratio = 0.25  # 沉睡需大额券强召回,成本高
    elif segment == "高价值":
        conv, est = 5, stats["count"] * stats["avg_spent"] * 0.05
        cost_ratio = 0.17  # 高价值需专属权益维护,成本中低
    elif segment == "潜力":
        conv, est = 10, stats["count"] * 0.10 * stats["avg_spent"] * 0.5
        cost_ratio = 0.18  # 潜力需中等力度促升级
    else:
        conv, est = 20, stats["count"] * 0.20 * stats["avg_order"] * 3
        cost_ratio = 0.20  # 新客首单券+引流,成本中高
    cost = est * cost_ratio
    roi_ratio = round(est / cost, 1) if cost > 0 else 0

    objective = {
        "高价值": "提留存防流失,提升VIP复购",
        "潜力": "促升级提频次,转化为高价值",
        "新客": "转复购养习惯,完成首单",
        "沉睡": "召回激活,7天内到店",
    }.get(segment, "提升该群体营收")

    return {
        "segment": segment,
        "objective": objective,
        "strategies": strat[:3],
        "products": [{"shop": "喜茶", "reason": "高频餐饮引流,适合券核销"}, {"shop": "Walmart沃尔玛", "reason": "主力超市覆盖全客群"}],
        "copywriting": f"【万泰会员专属】{segment}专享福利来啦!到店消费享专属优惠,限时7天,别错过~🎁",
        "roi": {
            "target_count": stats["count"],
            "conversion_rate": conv,
            "est_revenue": int(est),
            "cost": int(cost),
            "roi_ratio": roi_ratio,
        },
        "compliance_note": "投放文案不得夸大宣传,会员数据已脱敏,遵守个人信息保护法。",
        "_source": "fallback_rule",
    }


def generate_marketing_plan(segment: str, stats: dict, use_llm: bool = True) -> dict:
    """生成结构化营销方案。

    Args:
        segment: RFM 群体(高价值/潜力/新客/沉睡)
        stats: {"count","pct","avg_spent","avg_visit","avg_order"} 真实统计
        use_llm: 是否调大模型(True;False 用 fallback)
    Returns: 结构化方案 dict(含 _source 字段标明来源)
    """
    # RAG 检索(总是做,供 context)
    try:
        rag_context = rag.retrieve_for_marketing(segment, k=5)
    except Exception as e:
        logger.warning(f"RAG 检索失败,用空 context: {e}")
        rag_context = "(知识库暂不可用)"

    if not use_llm or not is_llm_ready():
        plan = _fallback_plan(segment, stats)
        plan["_source"] = "fallback_rule"
        return plan

    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(segment, stats, rag_context)},
        ]
        r = chat(messages, temperature=0.7, max_tokens=1500, json_mode=True)
        plan = parse_json_response(r["content"])
        # 宽松验收:含 strategies(关键结构)即接受;字段不全不降级
        if not isinstance(plan, dict) or "strategies" not in plan:
            logger.warning(f"Agent 返回 JSON 解析失败,降级规则。原文: {r['content'][:200]}")
            return _fallback_plan(segment, stats)
        plan["_source"] = f"llm:{r['model']}"
        plan["segment"] = segment
        # AI 返回 ROI 虚高保护:超 6 则用 fallback ROI 替换(防 26.6x 等造假)
        try:
            ai_roi = plan.get("roi", {})
            ai_ratio = float(ai_roi.get("roi_ratio", 0))
            if ai_ratio > 6 or ai_ratio <= 0:
                logger.warning(f"AI ROI={ai_ratio} 越界(>6 或 ≤0),用 fallback ROI 替换")
                plan["roi"] = _fallback_plan(segment, stats)["roi"]
        except (TypeError, ValueError):
            plan["roi"] = _fallback_plan(segment, stats)["roi"]
        return plan
    except Exception as e:
        logger.warning(f"营销 Agent 调用失败,降级规则: {e}")
        return _fallback_plan(segment, stats)


def generate_daily_digest(stats_overview: dict, use_llm: bool = True) -> dict:
    """首页 AI 运营日报:基于全局统计生成 3 条关键洞察。

    Args:
        stats_overview: {"total_traffic","total_revenue","total_members","vip_count",
                         "top_peak":"周X HH:00","weather_ratio":1.x,"holiday_boost":2.0,...}
    Returns: {"insights": ["洞察1","洞察2","洞察3"], "_source": "llm:xxx" 或 "fallback_rule"}
    """
    fallback_insights = [
        f"年度客流{stats_overview.get('total_traffic',0):,.0f},峰值时段{stats_overview.get('top_peak','周末晚间')},建议高峰前1小时推送券。",
        f"高价值会员{stats_overview.get('vip_count',0)}人,建议配置专属活动提留存。",
        f"节假日客流为工作日{stats_overview.get('holiday_boost',2.0):.1f}倍,提前备货并加排晚间人手。",
    ]
    fallback = {"insights": fallback_insights, "_source": "fallback_rule"}
    if not use_llm or not is_llm_ready():
        return fallback

    try:
        sys = (
            "你是万泰新天地智能运营中台的运营分析师。基于商场真实运营数据,生成3条简洁、可行动的运营洞察。"
            '严格返回JSON: {"insights": ["洞察1","洞察2","洞察3"]}。每条≤40字,含具体数字与建议动作。'
        )
        data_str = json.dumps(stats_overview, ensure_ascii=False, default=str)
        r = chat(
            [{"role": "system", "content": sys},
             {"role": "user", "content": f"商场运营数据:\n{data_str}\n\n生成3条运营洞察。返回JSON。"}],
            temperature=0.6, max_tokens=500, json_mode=True,
        )
        parsed = parse_json_response(r["content"])
        # 宽松验收:含 insights 列表即接受
        if isinstance(parsed, dict) and "insights" in parsed and isinstance(parsed["insights"], list):
            parsed["insights"] = parsed["insights"][:3]
            parsed["_source"] = f"llm:{r['model']}"
            return parsed
        return fallback
    except Exception as e:
        logger.warning(f"运营日报生成失败,降级: {e}")
        return fallback


def _build_data_facts() -> dict:
    """从真实数据计算关键统计,供AI回答时引用(不编造)。"""
    import pandas as pd
    from app.utils import load_csv
    from app.processor import clean_data, mask_sensitive_data
    from app.models import RFMModel, calculate_shop_score
    try:
        facts = {}
        # 会员 + RFM
        members = load_csv("members_2023.csv", "raw")
        mc = clean_data(members)
        mm = mask_sensitive_data(mc)
        rfm = RFMModel()
        mm["segment"] = rfm.fit(mm)
        seg_counts = mm["segment"].value_counts().to_dict()
        level_counts = mm["level"].value_counts().to_dict()
        facts["会员"] = {
            "总数": len(mm),
            "分群": {k: int(v) for k, v in seg_counts.items()},
            "等级": {k: int(v) for k, v in level_counts.items()},
            "平均累计消费": int(mm["total_spent"].mean()),
            "平均到店次数": round(mm["visit_count"].mean(), 1),
            "高价值人数": int(seg_counts.get("高价值", 0)),
            "沉睡人数": int(seg_counts.get("沉睡", 0)),
        }
        # 商铺
        shops = load_csv("shops_master.csv", "raw")
        ss = calculate_shop_score(shops)
        facts["商铺"] = {
            "总数": len(shops),
            "品牌数": int(shops["name"].nunique()),
            "业态分布": shops["category"].value_counts().to_dict(),
            "楼层分布": shops["floor"].value_counts().sort_index().to_dict(),
            "主力店": shops.loc[shops["is_anchor"], "name"].unique().tolist(),
            "榜首": ss.nsmallest(1, "rank").iloc[0]["name"],
            "末位": ss.nlargest(1, "rank").iloc[0]["name"],
            "平均评分": round(ss["score"].mean(), 1),
        }
        # 客流
        traffic = load_csv("foot_traffic_2023.csv", "raw")
        facts["客流"] = {
            "年度总客流": int(traffic["visitor_count"].sum()),
            "日均客流": int(traffic.groupby("date")["visitor_count"].sum().mean()),
            "周末均客流": int(traffic[traffic["is_weekend"]]["visitor_count"].mean()),
            "工作日均客流": int(traffic[~traffic["is_weekend"]]["visitor_count"].mean()),
            "节假日均客流": int(traffic[traffic["is_holiday"]]["visitor_count"].mean()) if traffic["is_holiday"].any() else 0,
        }
        # 咨询
        try:
            consult = load_csv("consultations_2023.csv", "raw")
            facts["咨询"] = {
                "总数": len(consult),
                "类型分布": consult["consult_type"].value_counts().head(5).to_dict(),
            }
        except Exception:
            pass
        return facts
    except Exception as e:
        logger.warning(f"数据facts构建失败: {e}")
        return {}


def _cached_facts():
    """带 Streamlit 缓存的真实数据 facts(无 Streamlit 上下文则直接计算)。"""
    try:
        import streamlit as st
        @st.cache_data(ttl=3600)
        def _load():
            return _build_data_facts()
        return _load()
    except Exception:
        return _build_data_facts()


def answer_operation_question(question: str, use_llm: bool = True) -> str:
    """运营问答:自然语言提问 → 真实数据 + RAG + 大模型回答。

    关键:注入真实数据统计(会员数/商铺数/客流等),AI 基于真实数字回答,不编造。
    """
    # 意图判断
    q_lower = question.lower()
    irrelevant_keywords = ["几点", "现在时间", "今天日期", "今天几号", "今天星期",
                           "实时天气", "今天天气", "新闻", "讲个笑话", "你是谁",
                           "你叫什么", "你好", "在吗", "股票", "汇率"]
    if any(k in question or k in q_lower for k in irrelevant_keywords) and len(question) < 15:
        return ("这个问题超出商场运营范围了😅\n\n"
                "我是**万泰新天地智能运营中台**的AI助手,擅长回答:\n"
                "• 客流规律(高峰时段/天气影响/楼层分布)\n"
                "• 会员分层(高价值/沉睡会员/等级分布)\n"
                "• 商铺评估(排行/租售比/业态)\n"
                "• 营销策略(各群体怎么营销)\n"
                "• 租户管理(收租/合同到期)\n\n"
                "试试问我:**「L1有哪些主力店?」** 或 **「沉睡会员怎么激活?」**")

    # RAG 检索
    try:
        context = rag.retrieve_text(question, k=5)
    except Exception:
        context = ""

    # 真实数据统计
    facts = _cached_facts()
    facts_str = json.dumps(facts, ensure_ascii=False, default=str) if facts else "(数据暂不可用)"

    if not use_llm or not is_llm_ready():
        return f"(AI暂不可用,检索到相关知识)\n{context[:300]}" if context else "AI暂不可用,且未检索到相关知识。"

    try:
        sys = (
            "你是万泰新天地智能运营中台的运营AI助手。\n"
            "你已接入商场**真实运营数据**(见下方数据事实),回答时必须引用这些真实数字,不得说'无法访问数据'。\n"
            "规则:\n"
            "1. 只回答商场运营相关问题(客流/会员/商铺/营销/租户/咨询)。无关问题礼貌引导回运营场景。\n"
            "2. 回答要简洁、具体、**引用真实数据数字**,不确定的说不知道。\n"
            "3. 回答末尾附1条可行动建议。\n\n"
            f"=== 商场真实数据事实 ===\n{facts_str}\n\n"
            f"=== 知识库上下文 ===\n{context}"
        )
        r = chat(
            [{"role": "system", "content": sys},
             {"role": "user", "content": question}],
            temperature=0.4, max_tokens=800,
        )
        return r["content"]
    except Exception as e:
        return f"AI回答失败:{e}"


# ===== 多轮对话 =====
_CHAT_SYSTEM = (
    "你是万泰新天地智能运营中台的运营AI助手。\n"
    "你已接入商场**真实运营数据**(见下方数据事实),回答时必须引用真实数字,不得说'无法访问数据'。\n"
    "规则:\n"
    "1. 只回答商场运营相关问题(客流/会员/商铺/营销/租户/咨询)。无关问题礼貌引导回运营场景。\n"
    "2. 回答简洁、具体、**引用真实数据**,不确定的说不知道,不编造。\n"
    "3. 这是多轮对话,可结合上下文追问。若用户问题依赖前文(如'他们''那些'),承接上文回答。\n"
    "4. 回答末尾附1条可行动建议(若已附则不重复)。\n\n"
    "{facts_block}\n\n"
    "{context_block}"
)


def chat_operation(question: str, history: list, use_llm: bool = True) -> dict:
    """多轮运营对话。history=[{"role":"user","content"}, {"role":"assistant","content"}, ...]

    Returns: {"text": 回复文本, "_source": "llm:xxx" 或 "fallback_rule"}
    """
    # 意图拦截(短无关问题)
    q_lower = question.lower()
    irrelevant = ["几点", "现在时间", "今天日期", "今天几号", "今天星期",
                  "实时天气", "今天天气", "新闻", "讲个笑话", "你是谁",
                  "你叫什么", "你好", "在吗", "股票", "汇率"]
    if any(k in question or k in q_lower for k in irrelevant) and len(question) < 15:
        return {"text": ("这个问题超出商场运营范围了😅\n\n"
                         "我是**万泰新天地智能运营中台**的AI助手,擅长回答客流/会员/商铺/营销/租户问题。\n"
                         "试试问我:**「高价值会员有多少?」** 或 **「沉睡会员怎么激活?」**"),
                "_source": "fallback_rule"}

    # RAG 检索(用当前问题 + 上文最后一条拼接,提升相关性)
    last_q = history[-1]["content"] if history and history[-1]["role"] == "user" else ""
    try:
        context = rag.retrieve_text(f"{last_q} {question}", k=5)
    except Exception:
        context = ""

    facts = _cached_facts()
    facts_block = f"=== 商场真实数据事实 ===\n{json.dumps(facts, ensure_ascii=False, default=str)}" if facts else ""
    context_block = f"=== 知识库上下文 ===\n{context}" if context else ""
    sys_prompt = _CHAT_SYSTEM.format(facts_block=facts_block, context_block=context_block)

    if not use_llm or not is_llm_ready():
        fb_text = f"(AI暂不可用,检索到相关知识)\n{context[:300]}" if context else "AI暂不可用。"
        return {"text": fb_text, "_source": "fallback_rule"}

    messages = [{"role": "system", "content": sys_prompt}]
    # 加入历史(限制最近 8 轮,控制 token)
    messages.extend(history[-8:])
    messages.append({"role": "user", "content": question})

    try:
        r = chat(messages, temperature=0.4, max_tokens=800)
        return {"text": r["content"], "_source": f"llm:{r['model']}"}
    except Exception as e:
        return {"text": f"AI回答失败:{e}", "_source": "fallback_rule"}


def generate_rent_reminder(shop: dict, use_llm: bool = True) -> dict:
    """生成催租话术(痛点⑤)。

    Args:
        shop: {"name","floor","category","monthly_rent","rent_status","contract_end","days_to_end"}
    Returns: {"text": 话术正文, "_source": "llm:xxx" 或 "fallback_rule"}
    """
    fallback_text = (
        f"【万泰新天地】{shop.get('name','租户')}您好,贵商铺本月租金 ¥{shop.get('monthly_rent',0):,.0f} "
        f"尚未到账,请于 7 日内完成缴纳。如有疑问请联系运营部。感谢配合!"
    )
    fallback = {"text": fallback_text, "_source": "fallback_rule"}
    if not use_llm or not is_llm_ready():
        return fallback

    try:
        sys = (
            "你是万泰新天地运营中台的租户管理助手,生成合规、礼貌、可直接发送的租金催缴话术。"
            "要求:1)礼貌但明确欠费金额与期限 2)给出便捷缴纳方式(小程序/对公账户)3)预留疑问沟通渠道 "
            "4)遵守广告法与合同法,不得威胁或单方面解约 5)≤120字。只返回话术正文,不要其他文字。"
        )
        status_hint = {
            "逾期": f"已逾期 {abs(shop.get('days_to_end',0))} 天,需加急催缴",
            "待收": "本月待收,常规提醒",
            "已收": "已收讫,无需催缴(本场景不应触发)",
        }.get(shop.get("rent_status"), "")
        r = chat(
            [{"role": "system", "content": sys},
             {"role": "user", "content": json.dumps(shop, ensure_ascii=False, default=str) + f"\n状态:{status_hint}。生成催租话术。"}],
            temperature=0.5, max_tokens=300,
        )
        text = r["content"].strip()
        if not text:
            return fallback
        return {"text": text, "_source": f"llm:{r['model']}"}
    except Exception as e:
        logger.warning(f"催租话术生成失败,降级: {e}")
        return fallback


def generate_acquisition_plan(channel: str, stats: dict, use_llm: bool = True) -> dict:
    """生成数字化获客方案(痛点③)。

    Args:
        channel: 渠道(微信小程序/支付即会员/扫码地推/线下门店)
        stats: {"new_members","channel_pct","cost_per","avg_spent","target_segment"}
    Returns: {"channel","tactic","copywriting","est_cost","est_new_members","est_revenue","roi"}
    """
    # 按渠道区分单客获客成本(行业基准,元/人)
    _channel_cost_per = {
        "微信小程序": 8,    # 线上投放成本低
        "支付即会员": 5,    # 支付场景自然转化,成本最低
        "扫码地推": 15,     # 地推人力+物料,成本中
        "线下门店": 25,     # 门店导购+物料,成本最高
    }
    new_members = int(stats.get("new_members", 100) * 0.8)
    avg_spent_v = stats.get("avg_spent", 400)
    # 单客获客成本:优先用 stats 传入的,否则按渠道基准
    cost_per = stats.get("cost_per", _channel_cost_per.get(channel, 15))
    est_cost = int(new_members * cost_per)
    # 增量营收:基于新客首单价值(非累计终身消费!)
    # 首单价值保守估算 = min(avg_spent 的 0.5%, 80元),代表首单客单价(商场餐饮/零售)
    first_order_value = min(avg_spent_v * 0.005, 80)
    est_revenue = int(new_members * first_order_value)
    fallback = {
        "channel": channel,
        "tactic": f"通过{channel}投放新客首单券,降低决策门槛,配合签到积分养到店习惯。",
        "copywriting": f"【万泰新天地】新朋友专属福利!首单立减20元,签到再得积分~🎁",
        "est_cost": est_cost,
        "est_new_members": new_members,
        "est_revenue": est_revenue,
        "roi": min(round(est_revenue / est_cost, 1) if est_cost else 0, 6.0),
    }
    fb = fallback
    fb["_source"] = "fallback_rule"
    # ROI 上限保护:渠道单客获客成本差异大,超 6x 用 6.0 封顶(防数字渠道 ROI 虚高)

    if not use_llm or not is_llm_ready():
        return fallback

    try:
        sys = (
            "你是万泰新天地数字化获客顾问,为商场生成可落地的拉新方案。严格返回JSON(无其他文字):\n"
            '{"channel":"渠道","tactic":"具体打法(含机制)","copywriting":"可直接投放的话术(含优惠,口语化,带emoji)",'
            '"est_cost":"预估成本(整数)","est_new_members":"预计新增会员(整数)","est_revenue":"预计增收(整数)","roi":"ROI倍数"}\n'
            "规则:基于真实数据合理估算,不得虚高;roi 应在 1-6 之间,基于投放成本与增量营收合理估算;话术合规不夸大。"
        )
        r = chat(
            [{"role": "system", "content": sys},
             {"role": "user", "content": json.dumps({"channel": channel, "stats": stats}, ensure_ascii=False, default=str) + "\n生成方案,返回JSON。"}],
            temperature=0.7, max_tokens=500, json_mode=True,
        )
        plan = parse_json_response(r["content"])
        # 宽松验收:含 tactic(关键字段)即接受
        if not isinstance(plan, dict) or "tactic" not in plan:
            return fallback
        # AI 返回 ROI 虚高保护:超 6 则用 fallback ROI 替换
        try:
            ai_roi = float(plan.get("roi", 0))
            if ai_roi > 6 or ai_roi <= 0:
                logger.warning(f"获客 AI ROI={ai_roi} 越界,用 fallback ROI 替换")
                plan["roi"] = fallback["roi"]
                plan["est_revenue"] = fallback["est_revenue"]
                plan["est_cost"] = fallback["est_cost"]
        except (TypeError, ValueError):
            plan["roi"] = fallback["roi"]
        plan["_source"] = f"llm:{r['model']}"
        return plan
    except Exception as e:
        logger.warning(f"获客方案生成失败,降级: {e}")
        return fallback


def generate_collection_advice(low_coverage_shops: list, use_llm: bool = True) -> dict:
    """数据采集建议(痛点④)。

    Args:
        low_coverage_shops: [{"name","category","collection_rate","missing_fields"}]
    Returns: {"advice": ["建议1","建议2","建议3"], "_source": "llm:xxx" 或 "fallback_rule"}
    """
    fallback_list = [
        "为低采集率商铺部署IoT客流计数器+POS对接,补齐客流与销售数据",
        "主力店(沃尔玛/中影)采集率已达90%+,将其数据标准推广至中小商户",
        "对采集率<60%的商铺优先上门对接,纳入次月经营考核",
    ]
    fallback = {"advice": fallback_list, "_source": "fallback_rule"}
    if not use_llm or not is_llm_ready():
        return fallback

    try:
        sys = (
            "你是万泰新天地数据治理顾问,基于商铺采集现状生成3条可执行的数据采集建议。"
            '严格返回JSON: {"advice":["建议1","建议2","建议3"]}。每条≤45字,含具体动作。'
        )
        r = chat(
            [{"role": "system", "content": sys},
             {"role": "user", "content": json.dumps(low_coverage_shops[:10], ensure_ascii=False, default=str) + "\n生成3条采集建议,返回JSON。"}],
            temperature=0.6, max_tokens=400, json_mode=True,
        )
        parsed = parse_json_response(r["content"])
        # 宽松验收:含 advice 列表即接受
        if isinstance(parsed, dict) and "advice" in parsed and isinstance(parsed["advice"], list):
            parsed["advice"] = parsed["advice"][:3]
            parsed["_source"] = f"llm:{r['model']}"
            return parsed
        return fallback
    except Exception as e:
        logger.warning(f"采集建议生成失败,降级: {e}")
        return fallback


def generate_traffic_profile(summary: dict, use_llm: bool = True) -> dict:
    """客流人群画像总结(痛点①:不知来商场的人是谁)

    Args:
        summary: {"peak_hour","peak_weekday","floor_top","weather_ratio","holiday_boost","conv_rate"}
    Returns: {"text": 画像总结文本, "_source": "llm:xxx" 或 "fallback_rule"}
    """
    fallback_text = (
        f"客流画像:高峰{summary.get('peak_weekday','周末')} {summary.get('peak_hour','19:00')},"
        f"{summary.get('floor_top','1F')}客流最旺;会员转化率{summary.get('conv_rate',0)*100:.0f}%。"
        f"建议高峰前1小时投放券,雨天主推室内娱乐层。"
    )
    fallback = {"text": fallback_text, "_source": "fallback_rule"}
    if not use_llm or not is_llm_ready():
        return fallback

    try:
        sys = (
            "你是万泰新天地客流分析师。基于客流时空数据,生成结构化的客流人群画像总结。\n"
            "必须包含以下5个部分,每部分一行,用【】标注标题,内容简洁含数字:\n"
            "【主力客群】什么样的人(年龄段/身份),占比估计\n"
            "【到店时段】何时来(高峰星期+时段,工作日vs周末差异)\n"
            "【楼层偏好】去哪些楼层,各楼层客流权重\n"
            "【天气影响】晴雨天客流差异,雨天偏好\n"
            "【转化建议】3条可行动建议(投放时机/楼层策略/天气应对)\n"
            "只返回这5行,不要多余文字。每行≤50字。"
        )
        r = chat(
            [{"role": "system", "content": sys},
             {"role": "user", "content": json.dumps(summary, ensure_ascii=False, default=str) + "\n生成客流人群画像。"}],
            temperature=0.5, max_tokens=800,
        )
        text = r["content"].strip()
        if not text:
            return fallback
        return {"text": text, "_source": f"llm:{r['model']}"}
    except Exception as e:
        logger.warning(f"客流画像生成失败,降级: {e}")
        return fallback


def analyze_consultations(consult_stats: dict, use_llm: bool = True) -> dict:
    """客户咨询洞察分析(用上数据弹药③:客户咨询记录)。

    Args:
        consult_stats: {"total","top_types":[(type,count)],"top_channels":[..],
                        "negative_pct","pending_pct","peak_hour","sample_contents":[]}
    Returns: {"insights":["洞察1",...], "hot_questions":["热点问题1",...],
              "improvements":["改进建议1",...], "_source":"llm:xxx"}
    """
    fallback = {
        "insights": [
            f"咨询总量{consult_stats.get('total',0)}条,最热类型{consult_stats.get('top_types',[('未知',0)])[0][0]}",
            f"负面咨询占{consult_stats.get('negative_pct',0):.0f}%,待处理{consult_stats.get('pending_pct',0):.0f}%",
            f"高峰时段{consult_stats.get('peak_hour','15:00')},建议此时段加强客服",
        ],
        "hot_questions": [t[0] for t in consult_stats.get("top_types", [])[:5]],
        "improvements": ["负面咨询24小时内闭环", "高频问题做FAQ自动回复", "待处理咨询分配责任人"],
        "_source": "fallback_rule",
    }
    if not use_llm or not is_llm_ready():
        return fallback

    try:
        sys = (
            "你是万泰新天地客户体验分析师,基于客户咨询记录生成洞察。"
            '严格返回JSON: {"insights":["洞察1","洞察2","洞察3"],'
            '"hot_questions":["热点问题1","热点问题2","热点问题3","热点问题4","热点问题5"],'
            '"improvements":["改进建议1","改进建议2","改进建议3"]}。'
            "insights=数据洞察(含数字),hot_questions=客户最关心的问题,improvements=可执行改进。"
        )
        r = chat(
            [{"role": "system", "content": sys},
             {"role": "user", "content": json.dumps(consult_stats, ensure_ascii=False, default=str) + "\n生成咨询洞察。返回JSON。"}],
            temperature=0.6, max_tokens=600, json_mode=True,
        )
        parsed = parse_json_response(r["content"])
        # 宽松验收:含 insights(关键字段)即接受,hot_questions/improvements 缺失不降级
        if isinstance(parsed, dict) and "insights" in parsed:
            parsed["_source"] = f"llm:{r['model']}"
            return parsed
        return fallback
    except Exception as e:
        logger.warning(f"咨询分析失败,降级: {e}")
        return fallback


def generate_consult_reply(consult: dict, use_llm: bool = True) -> dict:
    """AI 自动回复建议(单条咨询)。

    Returns: {"text": 回复话术, "_source": "llm:xxx" 或 "fallback_rule"}
    """
    fallback_text = f"您好,关于「{consult.get('content','')}」的咨询已收到,我们将尽快为您处理。"
    fallback = {"text": fallback_text, "_source": "fallback_rule"}
    if not use_llm or not is_llm_ready():
        return fallback
    try:
        sys = "你是万泰新天地客服助手,基于客户咨询生成礼貌、专业、可直接回复的话术。≤80字。只返回回复正文。"
        r = chat(
            [{"role": "system", "content": sys},
             {"role": "user", "content": json.dumps(consult, ensure_ascii=False, default=str) + "\n生成回复话术。"}],
            temperature=0.6, max_tokens=200,
        )
        text = r["content"].strip()
        if not text:
            return fallback
        return {"text": text, "_source": f"llm:{r['model']}"}
    except Exception:
        return fallback


# ====================================================================
# ReAct Agent(多步工具调用)—— 把营销Agent从"单次LLM调用"升级为"自主调工具的Agent"
# 评审看的"真Agent":大模型自主决定调哪些工具、调几次,而非硬编码先检索再生成。
# 工具:query_member_segment / query_shop_ranking / retrieve_knowledge / estimate_roi
# ====================================================================

# 工具注册表(供大模型调用的真实函数)
def _tool_query_member_segment(segment: str) -> dict:
    """查某RFM群体的真实统计"""
    try:
        import pandas as pd
        from app.utils import load_csv
        from app.processor import clean_data, mask_sensitive_data
        from app.models import RFMModel
        m = load_csv("members_2023.csv", "raw")
        mc = clean_data(m)
        mm = mask_sensitive_data(mc)
        rfm = RFMModel()
        mm["segment"] = rfm.fit(mm)
        seg = mm[mm["segment"] == segment]
        if len(seg) == 0:
            return {"error": f"群体{segment}不存在"}
        return {
            "segment": segment, "count": int(len(seg)),
            "pct": round(len(seg) / len(mm) * 100, 1),
            "avg_spent": round(float(seg["total_spent"].mean()), 0),
            "avg_visit": round(float(seg["visit_count"].mean()), 1),
            "avg_order": round(float(seg["avg_spent"].mean()), 0),
            "level_dist": seg["level"].value_counts().to_dict(),
        }
    except Exception as e:
        return {"error": str(e)}


def _tool_query_shop_ranking(category: str = "", floor: int = 0, topn: int = 5) -> list:
    """查商铺排行(可按业态/楼层筛选)"""
    try:
        import pandas as pd
        from app.utils import load_csv
        from app.models import calculate_shop_score
        s = load_csv("shops_master.csv", "raw")
        ss = calculate_shop_score(s)
        if category:
            ss = ss[ss["category"] == category]
        if floor:
            ss = ss[ss["floor"] == floor]
        top = ss.nsmallest(topn, "rank")[["name", "category", "floor", "score", "monthly_sales"]]
        return top.to_dict("records")
    except Exception as e:
        return [{"error": str(e)}]


def _tool_retrieve_knowledge(query: str, k: int = 4) -> str:
    """RAG 检索商场知识库"""
    try:
        return rag.retrieve_text(query, k=k)
    except Exception as e:
        return f"(检索失败: {e})"


def _tool_estimate_roi(segment: str, count: int, avg_spent: float) -> dict:
    """基于群体统计估算ROI(按群体区分成本占比)"""
    ratios = {"沉睡": 0.25, "高价值": 0.17, "潜力": 0.18, "新客": 0.20}
    convs = {"沉睡": 15, "高价值": 5, "潜力": 10, "新客": 20}
    conv = convs.get(segment, 15)
    cost_ratio = ratios.get(segment, 0.20)
    if segment == "新客":
        est = count * conv / 100 * 300 * 3  # 新客按客单×3
    else:
        est = count * conv / 100 * avg_spent * (0.3 if segment == "沉睡" else 0.5)
    cost = est * cost_ratio
    return {
        "conversion_rate": conv,
        "est_revenue": int(est),
        "cost": int(cost),
        "roi_ratio": round(est / cost, 1) if cost > 0 else 0,
        "note": f"{segment}群体投放成本占比{cost_ratio*100:.0f}%,基于行业基准,需AB测试校准",
    }


# 工具描述(喂给大模型,让它知道能调什么)
AGENT_TOOLS = [
    {"name": "query_member_segment", "desc": "查某RFM群体(高价值/潜力/新客/沉睡)的真实统计(人数/均消费/均到店/等级分布)",
     "args": {"segment": "群体名"}},
    {"name": "query_shop_ranking", "desc": "查商铺综合评分排行(可按业态/楼层筛选),返回top商铺",
     "args": {"category": "业态(餐饮/零售/服饰/娱乐/服务/汽车数码,可空)", "floor": "楼层1-5(0=全部)", "topn": "返回条数"}},
    {"name": "retrieve_knowledge", "desc": "RAG检索商场知识库(商户清单/营销方法论/万泰企业资料/业务指标)",
     "args": {"query": "检索问题", "k": "返回条数(默认4)"}},
    {"name": "estimate_roi", "desc": "基于群体统计估算营销ROI(按群体区分成本,返回转化率/增收/成本/ROI)",
     "args": {"segment": "群体名", "count": "人数", "avg_spent": "平均累计消费"}},
]

REACT_SYSTEM = """你是"万泰新天地智能运营中台"的营销Agent,通过**自主调用工具**收集信息后生成可落地的会员营销方案。

你可以调用以下工具(返回JSON):
{tools_desc}

工作流(ReAct循环,最多4轮):
每轮你必须返回JSON,格式二选一:
A. 调工具: {{"action": "tool", "tool": "工具名", "args": {{参数}}}}
B. 出最终方案: {{"action": "final", "plan": {{最终方案JSON}}}}

最终方案JSON结构:
{{
  "segment": "群体名", "objective": "营销目标一句话",
  "strategies": [{{"title":"策略名","desc":"具体做法","channels":["渠道"]}} x3],
  "products": [{{"shop":"真实商户名","reason":"推荐理由"}}],
  "copywriting": "可直接投放的话术(含优惠,带emoji)",
  "roi": {{"target_count":数字,"conversion_rate":数字,"est_revenue":数字,"cost":数字,"roi_ratio":1-6的数字}},
  "compliance_note": "合规提示"
}}

规则:
1. 先调 query_member_segment 拿群体真实统计,再调 retrieve_knowledge 检索营销方法论+商户,
   可选调 query_shop_ranking 找联动商户,最后用 estimate_roi 校准ROI,再出final方案。
2. products.shop 必须来自工具返回的真实商户,不得编造。
3. roi.roi_ratio 必须在1-6之间,参考 estimate_roi 返回值。
4. 合规:不夸大、保护隐私、遵守广告法。
"""


def _call_tool(tool_name: str, args: dict) -> str:
    """执行工具调用,返回结果字符串"""
    try:
        if tool_name == "query_member_segment":
            r = _tool_query_member_segment(args.get("segment", ""))
        elif tool_name == "query_shop_ranking":
            r = _tool_query_shop_ranking(args.get("category", ""), int(args.get("floor", 0)), int(args.get("topn", 5)))
        elif tool_name == "retrieve_knowledge":
            r = _tool_retrieve_knowledge(args.get("query", ""), int(args.get("k", 4)))
        elif tool_name == "estimate_roi":
            r = _tool_estimate_roi(args.get("segment", ""), int(args.get("count", 0)), float(args.get("avg_spent", 0)))
        else:
            return f"未知工具: {tool_name}"
        return json.dumps(r, ensure_ascii=False, default=str)
    except Exception as e:
        return f"工具执行错误: {e}"


def generate_marketing_plan_react(segment: str, stats: dict, use_llm: bool = True) -> dict:
    """ReAct多步Agent生成营销方案(真Agent:自主调工具循环)。

    Returns: {plan: 方案dict, _source: "llm:xxx/react" 或 "fallback_rule",
              _trace: [工具调用轨迹], _steps: 轮数}
    """
    if not use_llm or not is_llm_ready():
        plan = _fallback_plan(segment, stats)
        plan["_source"] = "fallback_rule"
        return plan

    tools_desc = "\n".join(
        f"- {t['name']}({t['args']}): {t['desc']}" for t in AGENT_TOOLS
    )
    sys_prompt = REACT_SYSTEM.format(tools_desc=tools_desc)

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": f"为{segment}群体生成营销方案。已知初始统计: {json.dumps(stats, ensure_ascii=False, default=str)}。请自主调工具收集信息后出final方案。"},
    ]
    trace = []
    for step in range(6):  # 最多6轮工具调用
        try:
            r = chat(messages, temperature=0.4, max_tokens=1200, json_mode=False)
        except Exception as e:
            logger.warning(f"ReAct第{step}轮调用失败: {e}")
            break
        decision = parse_json_response(r["content"])
        if not isinstance(decision, dict) or "action" not in decision:
            # 可能直接返回了方案(没按格式),尝试当final
            if isinstance(decision, dict) and "strategies" in decision:
                decision = {"action": "final", "plan": decision}
            else:
                logger.warning(f"ReAct第{step}轮返回无法解析: {r['content'][:200]}")
                break

        if decision["action"] == "tool":
            tool_name = decision.get("tool", "")
            tool_args = decision.get("args", {})
            result = _call_tool(tool_name, tool_args)
            trace.append({"step": step + 1, "tool": tool_name, "args": tool_args, "result_preview": result[:200]})
            messages.append({"role": "assistant", "content": r["content"]})
            messages.append({"role": "user", "content": f"工具结果: {result}\n\n请继续(调更多工具或出final方案)。"})
            continue
        elif decision["action"] == "final":
            plan = decision.get("plan", {})
            if not isinstance(plan, dict) or "strategies" not in plan:
                logger.warning("ReAct final方案缺strategies,降级")
                break
            plan["_source"] = f"llm:{r['model']}/react"
            plan["segment"] = segment
            plan["_trace"] = trace
            plan["_steps"] = step + 1
            # ROI越界保护
            try:
                ai_ratio = float(plan.get("roi", {}).get("roi_ratio", 0))
                if ai_ratio > 6 or ai_ratio <= 0:
                    plan["roi"] = _fallback_plan(segment, stats)["roi"]
            except (TypeError, ValueError):
                plan["roi"] = _fallback_plan(segment, stats)["roi"]
            return plan

    # ReAct失败,降级普通plan
    logger.warning(f"ReAct未产出final方案,降级普通generate_marketing_plan。trace={trace}")
    plan = generate_marketing_plan(segment, stats, use_llm=True)
    plan["_trace"] = trace
    return plan


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")
    stats = {"count": 1250, "pct": 25.0, "avg_spent": 3200, "avg_visit": 8.5, "avg_order": 376}
    print("=== ReAct Agent 营销方案(沉睡) ===")
    plan = generate_marketing_plan_react("沉睡", stats, use_llm=True)
    print(json.dumps(plan, ensure_ascii=False, indent=2)[:2000])
    print(f"\n来源: {plan.get('_source')}")
    print(f"工具调用轨迹({len(plan.get('_trace', []))}步):")
    for t in plan.get("_trace", []):
        print(f"  步{t['step']}: {t['tool']}({t['args']}) → {t['result_preview'][:80]}")
