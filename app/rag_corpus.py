"""RAG 知识库语料源 —— 4 类知识,供营销 Agent / 运营问答检索

语料来源:
  1. 真实商户清单(app/shops_data 生成)
  2. 万泰企业资料(企业弹药库 docx 的 4.1~4.5)
  3. 营销方法论(RFM/商铺评分/分层策略)
  4. 业务指标体系(各指标定义)

每条 chunk: {"id","category","title","text"}
build_corpus() 返回 list[dict],供 rag.py 向量化。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.shops_data import ALL_SHOPS, SHOPS_BY_FLOOR, unique_brand_count
from app.config import SHOP_WEIGHTS, FLOOR_TRAFFIC_WEIGHT, MALL_NAME, MALL_AREA_SQM, FLOORS


def _shop_chunks() -> list:
    """商户知识 chunks —— 每户一条 + 楼层汇总条"""
    chunks = []
    # 每个商户一条
    cat_brand_count = {}
    for s in ALL_SHOPS:
        cat_brand_count.setdefault(s.category, set()).add(s.name)
        text = (
            f"商户:{s.name},业态:{s.category},楼层:{s.floor}F,"
            f"品牌类型:{s.brand_type},{'主力店(强引流)' if s.is_anchor else '非主力店'},"
            f"面积约{s.area_sqm}㎡"
        )
        if s.note:
            text += f",备注:{s.note}"
        # 营销定位提示
        if s.category == "餐饮":
            text += "。营销定位:高频到店、复购驱动,适合券+会员日+饮品套餐"
        elif s.category == "零售":
            text += "。营销定位:客单高、决策周期长,适合满赠+积分+新品预览"
        elif s.category == "服饰":
            text += "。营销定位:季节性强、连带率高,适合换新季+搭配推荐+VIP预览"
        elif s.category == "娱乐":
            text += "。营销定位:体验型、引流强,适合亲子套餐+节假日票务+异业联动"
        elif s.category == "服务":
            text += "。营销定位:低频高粘,适合疗程卡+会员权益+转介奖励"
        elif s.category == "汽车数码":
            text += "。营销定位:高客单低频,适合试驾/体验+金融分期+以旧换新"
        chunks.append({
            "id": f"shop_{s.name}_{s.floor}F",
            "category": "商户清单",
            "title": s.name,
            "text": text,
        })
    # 楼层汇总
    for f in range(1, FLOORS + 1):
        ss = SHOPS_BY_FLOOR[f]
        cats = {}
        for s in ss:
            cats[s.category] = cats.get(s.category, 0) + 1
        cat_str = "、".join(f"{k}{v}家" for k, v in sorted(cats.items(), key=lambda x: -x[1]))
        anchors = [s.name for s in ss if s.is_anchor]
        text = f"{f}F(楼层{f})共{len(ss)}个商铺,业态分布:{cat_str}。"
        if anchors:
            text += f"主力店:{','.join(set(anchors))}。"
        if f == 1:
            text += "L1为客流入口层,零售餐饮服饰汽车数码混合,客流权重最高(1.0),适合品牌曝光与快消"
        elif f == 2:
            text += "L2以母婴童装服务为主,客流权重0.75,适合亲子家庭客群营销"
        elif f == 3:
            text += "L3餐饮+娱乐(KTV/密室),客流权重0.55,适合聚餐聚会场景"
        elif f == 4:
            text += "L4影院+KTV+餐饮,客流权重0.35,娱乐主力层,适合晚间/周末营销"
        elif f == 5:
            text += "L5纯娱乐(中影/魅力金座/金海),客流权重0.20,顶层引流,适合深度体验消费"
        chunks.append({
            "id": f"floor_{f}F",
            "category": "商户清单",
            "title": f"{f}F楼层概览",
            "text": text,
        })
    # 业态汇总
    for cat, brands in cat_brand_count.items():
        chunks.append({
            "id": f"cat_{cat}",
            "category": "商户清单",
            "title": f"{cat}业态",
            "text": f"{cat}业态共{len(brands)}个品牌:{'、'.join(sorted(brands))}",
        })
    return chunks


def _enterprise_chunks() -> list:
    """万泰企业资料 chunks(来源:企业弹药库 docx 4.1~4.5)"""
    return [
        {
            "id": "ent_intro",
            "category": "万泰企业",
            "title": "万泰新天地企业简介",
            "text": (
                "广东万泰集团旗下商业综合体项目,位于普宁市流沙北街道核心商圈"
                "(环城北路与广达路交汇处),毗邻普宁广场和国际服装城。"
                "万泰汇购物中心总建筑面积约20万平方米,2014年开业,"
                "集购物、休闲、娱乐、餐饮于一体,进驻优衣库、奈雪的茶、雅莹等品牌,"
                "是普宁体量最大、人气最旺的购物中心之一。万泰集团同时布局房地产开发、"
                "物业管理等业务,在普宁具有显著的城市运营影响力。"
                f"当前系统录入{unique_brand_count()}个真实品牌、{FLOORS}个楼层。"
            ),
        },
        {
            "id": "ent_pain",
            "category": "万泰企业",
            "title": "万泰核心痛点",
            "text": (
                "万泰新天地五大核心痛点:①不知来商场的人是谁——客流画像缺失,消费习惯不明;"
                "②线上线下会员不打通——营销割裂;③会员拉新靠传统方式——数字化获客不知道怎么做;"
                "④商铺经营数据采集不到——客流、销售数据缺失;⑤租户管理/合同管理繁琐——收租提醒靠人工。"
                "本系统针对①②③④设计:客流时空画像解决①,RFM会员分层解决②③,商铺评分解决④。"
            ),
        },
        {
            "id": "ent_data",
            "category": "万泰企业",
            "title": "万泰可用数据弹药",
            "text": "万泰可提供数据:客户咨询记录、商铺信息、会员数据(脱敏后)。合规边界:涉及消费者隐私保护、商业机密(租户信息)。系统所有会员手机号/姓名已脱敏(138****5678/王**),不存储身份证号。",
        },
        {
            "id": "ent_digital",
            "category": "万泰企业",
            "title": "万泰数字化基础",
            "text": "万泰技术负责人(集团技术负责人)掌管SaaS、OA、购房系统、财务系统、用户数据等全业务线数字化,数字化基础较完善。本系统可对接现有会员/商铺数据,落地可行性强。",
        },
    ]


def _methodology_chunks() -> list:
    """营销方法论 chunks"""
    w = SHOP_WEIGHTS
    return [
        {
            "id": "method_rfm",
            "category": "营销方法论",
            "title": "RFM会员分层模型",
            "text": (
                "RFM分群:R=最近到店天数(越小越好),F=到店次数(越大越好),M=累计消费(越大越好)。"
                "用K-Means聚类(K=4),按聚类中心综合评分(-R+F+M)降序动态映射标签,不硬编码。"
                "输出四类:高价值(近期+高频+高消费,核心利润来源)、"
                "潜力(消费力强但频次/近期待提升,升级空间大)、"
                "新客(刚注册/到店少,需培养习惯)、"
                "沉睡(长期未到店,需召回激活)。"
            ),
        },
        {
            "id": "method_segment_high",
            "category": "营销方法论",
            "title": "高价值会员营销策略",
            "text": "高价值会员(近期高频高消费)营销:VIP专属活动(品鉴会/私密沙龙)、积分双倍加速权益升级、新品限量预览、专属客户经理一对一。客单>5000元可推定制化推荐。目标:提留存、提客单、防流失。",
        },
        {
            "id": "method_segment_potential",
            "category": "营销方法论",
            "title": "潜力会员营销策略",
            "text": "潜力会员(消费力强但频次待提升)营销:升级权益引导(消费满额升级会员等级)、阶梯式满赠刺激客单价、关联品类推荐拓展消费广度。客单<2000元重点品类拓展。目标:促升级、提频次。",
        },
        {
            "id": "method_segment_new",
            "category": "营销方法论",
            "title": "新客营销策略",
            "text": "新客(注册/到店少)营销:首单立减降低决策门槛、每日签到得积分培养到店习惯、会员日邀请参与专属活动。目标:转复购、养习惯。",
        },
        {
            "id": "method_segment_sleep",
            "category": "营销方法论",
            "title": "沉睡会员营销策略",
            "text": "沉睡会员(长期未到店)营销:大额满减券激活消费、限时激活(7天内到店享专属礼包制造紧迫感)、个性化推荐基于历史偏好。到店<10次加推到店即赠热门商品体验装。目标:召回激活。",
        },
        {
            "id": "method_shop_score",
            "category": "营销方法论",
            "title": "商铺综合评分模型",
            "text": (
                f"商铺综合评分=0-100加权:销售{w['sales']*100:.0f}%+客流{w['traffic']*100:.0f}%+"
                f"租售比{w['rent_ratio']*100:.0f}%+会员转化{w['conversion']*100:.0f}%。"
                "各指标Min-Max归一化后加权求和。租售比=月租/中位数月租(相对租金贡献)。"
                "评分用于发现经营盲区:低分商铺需营销扶持或业态调整。"
            ),
        },
        {
            "id": "method_traffic",
            "category": "营销方法论",
            "title": "客流时空规律",
            "text": (
                "客流规律:周末客流为工作日1.4倍,节假日2.0倍,雨天降至0.8。"
                "工作日午高峰12-13点、晚高峰18-20点;周末全天10-21点高位。"
                f"楼层客流权重:{'、'.join(f'{f}F={v}' for f,v in FLOOR_TRAFFIC_WEIGHT.items())}(1F最高逐层递减)。"
                "营销建议:高峰时段前1小时推送券核销率最高;雨天主推室内娱乐(L4-L5)与餐饮。"
            ),
        },
        {
            "id": "method_roi",
            "category": "营销方法论",
            "title": "营销ROI预估方法",
            "text": "ROI预估:增量营收=目标人数×激活/转化率×人均贡献。沉睡激活率约15%人均贡献按历史消费30%;高价值留存提升5%;潜力升级10%人均消费50%;新客转化20%客单×3。投放成本按增量营收10-15%估。ROI>3为优质方案。",
        },
    ]


def _metric_chunks() -> list:
    """业务指标体系 chunks"""
    return [
        {"id": "metric_visitor_count", "category": "业务指标", "title": "客流(visitor_count)", "text": "客流visitor_count:某时段某楼层到店人次。系统按小时×楼层采样。年度总客流=全年各时段各楼层之和。高=人气旺。"},
        {"id": "metric_monthly_sales", "category": "业务指标", "title": "月销售额(monthly_sales)", "text": "月销售额monthly_sales:商铺当月销售额(元)。=坪效×面积。主力店(沃尔玛/中影)面积大总销售高但坪效低。"},
        {"id": "metric_conversion", "category": "业务指标", "title": "会员转化率(member_conversion_rate)", "text": "会员转化率member_conversion_rate:商铺客流中注册会员占比。餐饮偏高(15-35%)、服务偏低(3-10%)、沃尔玛超市最高(30-45%)。低转化=会员拉新空间大。"},
        {"id": "metric_rent_ratio", "category": "业务指标", "title": "租售比", "text": "租售比=月租金/月销售额。租售比过高(>30%)商铺经营压力大,需营销扶持或租金谈判。系统用相对租金贡献(月租/中位数月租)做评分。"},
        {"id": "metric_rfm_segment", "category": "业务指标", "title": "RFM分群(segment)", "text": "RFM分群segment:高价值/潜力/新客/沉睡四类。高价值=核心利润(近期高频高消费);沉睡=待召回(长期未到店)。营销资源应向高价值(留存)与沉睡(召回)倾斜。"},
        {"id": "metric_level", "category": "业务指标", "title": "会员等级(level)", "text": "会员等级level:普通/银卡/金卡/黑金。黑金2%(最高消费)、金卡13%、银卡25%、普通60%。黑金+金卡贡献大部分消费额,是VIP营销核心对象。"},
    ]


def _industry_case_chunks() -> list:
    """行业营销案例 chunks —— 提炼自真实行业营销方案库(800+文档)
    每条浓缩核心机制+万泰映射,供营销Agent检索真实玩法,避免泛泛而谈。
    """
    return [
        {
            "id": "case_clothing_positioning",
            "category": "行业营销案例",
            "title": "服装店定位与来人量提升(服饰品牌通用)",
            "text": (
                "服装店营销三定位:市场定位(明确店铺在消费者心中的形象/价格/经营理念)、"
                "客户定位(从坐销转行销,渗透销售每个环节,'来人量是成败关键',先明确目标客群再定产品组合/定价/服务/促销)、"
                "产品定位(细分分支特点评估市场)。万泰1-2F服饰层(NIKE/Adidas/雅莹/优衣库)应用:"
                "换新季主力店做搭配推荐+VIP预览,中岛店做连带率激励;店员从'等客'转'主动邀约会员',"
                "目标客群按会员RFM分层精准触达,提升来人量与连带率。"
            ),
        },
        {
            "id": "case_wechat_like",
            "category": "行业营销案例",
            "title": "微信集赞裂变拉新(低成本获客)",
            "text": (
                "集赞活动机制:用户转发活动到朋友圈并保持一周不删,根据集赞数兑换对应奖品。"
                "核心是'用户自主发起+好友点赞'实现裂变扩散,同时引导关注公众号/小程序成为会员。"
                "适用:新客拉新、活动预热、品牌曝光。万泰应用:小程序发起'集赞换喜茶券/中影影票',"
                "点赞门槛分级(38赞小券/68赞中券/128赞大券),裂变成本低、转化路径短,"
                "适合数字化获客(痛点③)。注意:奖品要有吸引力但成本可控,防刷单。"
            ),
        },
        {
            "id": "case_dual_weibo_wechat",
            "category": "行业营销案例",
            "title": "微博微信双平台矩阵运营(全渠道触达)",
            "text": (
                "双微矩阵:微信服务号(会员服务/券核销/在线客服,每月4次推送)、订阅号(内容营销/活动预告)、"
                "微博官微(品牌曝光/热点话题/活动直播)。职工号矩阵扩散。运营要点:内容差异化(服务号做功能,微博做话题),"
                "活动同步多平台,数据归一统一会员ID。万泰应用:服务号承载会员权益+券核销(对接POS),"
                "微博做商场活动/节日话题,#万泰新天地#话题运营,实现线上线下会员打通(痛点②)。"
            ),
        },
        {
            "id": "case_festival_dragonboat",
            "category": "行业营销案例",
            "title": "节日主题营销(端午节案例)",
            "text": (
                "节日营销模板:主题('万水千山粽是情')+传统节日文化体验+商家联动+广场聚集人气。"
                "机制:商场主办+商家协办,内容含传统习俗体验(包粽/香囊DIY)+品牌促销+会员专属福利。"
                "万泰应用:春节/端午/中秋/国庆四大节点做主题营销,L1中庭做体验区引流,餐饮层推节日套餐,"
                "零售层推节日满减,会员享积分双倍。节日客流为工作日2倍(已验证),提前一周预热+高峰前1小时推券。"
            ),
        },
        {
            "id": "case_word_of_mouth",
            "category": "行业营销案例",
            "title": "口碑营销五要素(饭店/餐饮通用)",
            "text": (
                "口碑营销五要素:借势、利益、新颖、争议、私密。三种传播途径:口耳相传(好产品服务为基础)、"
                "引发讨论(制造话题)、激励推荐(老带新奖励)。先识别'消费领袖'(创新型/前卫型消费者)重点维护。"
                "万泰应用:餐饮层(喜茶/星巴克/火锅)做'打卡晒单送券'激发口碑,识别高频会员做消费领袖给专属权益,"
                "老带新双方各得券(老会员带新会员,双方各得30元券),低成本裂变+高可信度。"
            ),
        },
        {
            "id": "case_roadshow",
            "category": "行业营销案例",
            "title": "路演活动执行框架(地产/商业项目)",
            "text": (
                "路演四要素:目的(聚人气+品牌口碑+积累有效客户)、时间(周末多场连办,下雨延期)、"
                "地点(人流密集宽阔场地)、形式(节目表演+项目讲解+有奖抢答+周边派单)。"
                "执行:提前1天物料到位,17:00布场19:00开始,销售统一工装接待登记,大兵团周边派单。"
                "万泰应用:L1中庭或外广场做周末路演,中影影城+主力店联动,节目+品牌讲解+会员注册有礼,"
                "周边社区派单引流,积累新会员(对接RFM新客分群)。"
            ),
        },
        {
            "id": "case_thanksgiving_draw",
            "category": "行业营销案例",
            "title": "感恩回馈抽奖活动(老客户激活)",
            "text": (
                "感恩回馈机制:老业主/老会员到场即抽奖,设吸引力奖品延长驻留时间促成交,电话CALL客通知。"
                "主题:'你敢梦我敢送'年终大派送。万泰应用:针对沉睡会员(>30天未到店)做感恩回馈召回,"
                "到场抽奖+专属优惠,电话/小程序精准触达沉睡群体,目的是7天内到店激活(对应沉睡分群营销目标)。"
                "奖品分级(阳光奖/幸运奖/大奖),成本可控但召回率高。"
            ),
        },
        {
            "id": "case_performance_atrium",
            "category": "行业营销案例",
            "title": "商场中庭演出活动(引流聚客)",
            "text": (
                "演出活动策划:主题(梦想启航/才艺汇演)+节目(团体舞/合唱/变脸/朗诵等约30个)+赞助商互动环节。"
                "目的:展示成果+提供展示舞台+家长沟通机会。万泰应用:L1主中庭定期办演出活动(少儿才艺/品牌发布/节日汇演),"
                "带动家庭客群到店,延长停留时间,关联餐饮/娱乐层消费。中影国际影城+教育类商户联动,"
                "活动+电影票+餐饮套餐组合销售,提升L4-5娱乐层客流(权重仅0.2-0.35,需活动引流)。"
            ),
        },
    ]


def build_corpus() -> list:
    """构建全部语料,返回 list[dict]"""
    return _shop_chunks() + _enterprise_chunks() + _methodology_chunks() + _metric_chunks() + _industry_case_chunks()


if __name__ == "__main__":
    c = build_corpus()
    print(f"语料总数: {len(c)}")
    from collections import Counter
    cats = Counter(x["category"] for x in c)
    print(f"分类: {dict(cats)}")
    print("\n--- 示例3条 ---")
    for x in c[:3]:
        print(f"[{x['category']}] {x['title']}: {x['text'][:80]}...")
