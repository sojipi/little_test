import gradio as gr
import json
import os
from typing import List
from openai import OpenAI
import requests
from PIL import Image
from io import BytesIO
import re

# 从环境变量读取API配置（更安全）
API_KEY = "ms-b064f11b-4b11-4ae0-a00e-ff98a69c9bd3"
BASE_URL = "https://api-inference.modelscope.cn/v1/"
MODEL_NAME = "deepseek-ai/DeepSeek-V3.2-Exp"

def init_openai_client():
    """初始化OpenAI客户端"""
    if not API_KEY:
        raise ValueError("请设置 MODELSCOPE_API_KEY 环境变量")
    return OpenAI(base_url=BASE_URL, api_key=API_KEY)

def clean_response(text):
    """清理响应文本，移除思考过程标记"""
    if not text:
        return ""
    # 移除 <thinking>...</thinking> 标签及内容
    text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL)
    # 移除其他可能的思考过程标记
    text = re.sub(r'\[?思考过程\]?:.*?(?=\n\n|\n【|\n=)', '', text, flags=re.DOTALL)
    # 清理多余的空行
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()

def validate_inputs(**kwargs):
    """验证输入参数"""
    for key, value in kwargs.items():
        if not value or str(value).strip() == "":
            return False, f"缺少必要参数: {key}"
    return True, ""

def generate_destination_recommendation(season, health_condition, budget, interests):
    """生成目的地推荐"""
    # 将兴趣列表转换为字符串
    if isinstance(interests, list):
        interests_str = "、".join(interests)
    else:
        interests_str = str(interests)

    # 验证输入
    is_valid, msg = validate_inputs(
        season=season, health_condition=health_condition,
        budget=budget, interests=interests_str
    )
    if not is_valid:
        return msg

    client = init_openai_client()
    system_prompt = """你是一个专业的老年旅行规划师。根据用户的季节、健康状况、预算和兴趣，推荐3-5个国内外热门适老目的地。

每个推荐应包括：
- 目的地名称
- 推荐理由（重点考虑避寒、康养、舒适度）
- 最佳旅行时长
- 注意事项（包括健康和安全建议）
- 舒适版活动示例

请用通俗易懂、温馨友好的语言回复，避免过于专业的术语。"""

    user_prompt = f"季节：{season}，健康状况：{health_condition}，预算：{budget}，兴趣偏好：{interests_str}"

    result = ""
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            stream=True,
            temperature=0.7,
            max_tokens=1500
        )
        for chunk in response:
            answer_chunk = chunk.choices[0].delta.content
            if answer_chunk:
                result += answer_chunk
        result = clean_response(result)

        # 如果结果为空，返回友好提示
        if not result.strip():
            result = "抱歉，暂时无法生成推荐，请稍后再试或检查网络连接。"

    except Exception as e:
        result = f"[错误] 生成推荐时出错：{str(e)}\n\n请检查：\n1. API密钥是否正确\n2. 网络连接是否正常\n3. API服务是否可用"

    return result

def generate_itinerary_plan(destination, duration, mobility, health_focus):
    """生成行程规划"""
    # 将健康关注点列表转换为字符串
    if isinstance(health_focus, list):
        health_focus_str = "、".join(health_focus)
    else:
        health_focus_str = str(health_focus)

    is_valid, msg = validate_inputs(destination=destination, duration=duration)
    if not is_valid:
        return msg

    client = init_openai_client()
    system_prompt = """你是一个经验丰富的老年旅行行程规划师。请为老年人制定舒缓、贴心的日行程安排。

要求：
- 每天安排半日活动、半日休息
- 避免高强度行程
- 包含健康提示和注意事项
- 提供备用方案（雨天等）
- 语言亲切温和
- 每天推荐具体的酒店名称（至少1-2家，包含酒店全名、地址、价格区间）
- 酒店推荐要考虑老年人需求：交通便利、环境安静、设施完善、靠近医院或公园"""

    user_prompt = f"""目的地：{destination}
旅行时长：{duration}
行动能力：{mobility}
健康关注点：{health_focus_str}"""

    result = ""
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            stream=True,
            temperature=0.7,
            max_tokens=2000
        )
        for chunk in response:
            answer_chunk = chunk.choices[0].delta.content
            if answer_chunk:
                result += answer_chunk
        result = clean_response(result)

        if not result.strip():
            result = "抱歉，暂时无法生成行程，请稍后再试。"

    except Exception as e:
        result = f"[错误] 生成行程时出错：{str(e)}"

    return result

def generate_checklist(destination, duration, special_needs, itinerary_content=None):
    """生成旅行清单（结构化数据）"""
    # 生成唯一ID用于保存
    import time
    import json
    import re
    checklist_id = f"{destination}_{duration}_{int(time.time())}"

    is_valid, msg = validate_inputs(destination=destination, duration=duration)
    if not is_valid:
        return msg

    # 从行程规划中提取酒店信息
    hotels = []
    if itinerary_content:
        # 简单的酒店名称提取（查找常见酒店关键词）
        hotel_patterns = [
            r'酒店[：:]\s*([^\n，,。.]+)',
            r'推荐酒店[：:]\s*([^\n，,。.]+)',
            r'([^\n，,。.]*(?:酒店|宾馆|度假村|客栈)[^\n，,。.]*)',
            r'([^\n，,。.]*(?:Hotel|Resort|Inn)[^\n，,。.]*)'
        ]
        for pattern in hotel_patterns:
            matches = re.findall(pattern, itinerary_content, re.IGNORECASE)
            hotels.extend(matches)
        # 去重并限制数量
        hotels = list(dict.fromkeys(hotels))[:10]

    client = init_openai_client()
    system_prompt = """你是一个专业的老年旅行助手。请为老年人制定详细的行前准备清单，包含交通、酒店、景点预订指引。

请以JSON格式返回，包含以下结构：
{
  "checklist": [
    {
      "category": "证件类",
      "items": [
        {"name": "物品名称", "required": true, "note": "备注说明"}
      ]
    }
  ],
  "booking_guides": {
    "transport": {
      "guide": "交通预订指引文字",
      "platforms": ["推荐平台1", "推荐平台2"]
    },
    "hotel": {
      "guide": "酒店预订指引文字",
      "platforms": ["推荐平台1", "推荐平台2"]
    },
    "attractions": {
      "guide": "景点预订指引文字",
      "platforms": ["推荐平台1", "推荐平台2"]
    }
  },
  "tips": ["温馨提示1", "温馨提示2"]
}

清单类别应包括：
1. 证件类 - 身份证、护照、签证、医保卡等
2. 药品类 - 常用药、处方药、急救药等
3. 衣物类 - 根据目的地气候准备
4. 电子设备 - 手机、充电器、转换插头等
5. 日用品 - 洗护用品、眼镜、助行器等
6. **交通预定** - 机票/火车票确认单、接送服务、当地交通卡等
7. **酒店预定** - 酒店确认单、入住须知、特殊需求说明等（重点突出具体酒店名称）
8. **景点门票** - 景点门票预约、导游服务、演出票等

每个类别列出具体物品，标注【必带】(required: true)和【可选】(required: false)。
特别是交通、酒店、景点类别，要列出需要提前准备和预定的具体清单项目。
如果提供了具体酒店信息，请在"酒店预定"类别中详细列出每个酒店的预订准备工作。
交通、酒店、景点指引要详细具体，包含预订流程和推荐平台。
只返回JSON，不要其他文字。"""

    user_prompt = f"目的地：{destination}，旅行时长：{duration}，特殊需求：{special_needs}\n"
    if hotels:
        user_prompt += f"行程规划中提到的酒店：{', '.join(hotels)}"

    result = ""
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            stream=True,
            temperature=0.6,
            max_tokens=2000
        )
        for chunk in response:
            answer_chunk = chunk.choices[0].delta.content
            if answer_chunk:
                result += answer_chunk
        result = clean_response(result)

        if not result.strip():
            result = "抱歉，暂时无法生成清单，请稍后再试。"
            return result

        # 尝试解析JSON
        try:
            import json
            # 提取JSON部分（处理可能的markdown代码块）
            json_match = None
            if "```json" in result:
                json_match = result.split("```json")[1].split("```")[0].strip()
            elif "```" in result:
                json_match = result.split("```")[1].split("```")[0].strip()
            else:
                json_match = result.strip()

            data = json.loads(json_match)

            # 保存到本地
            save_checklist_data(checklist_id, destination, duration, data)

            # 格式化为可读文本
            formatted_result = format_checklist_output(checklist_id, destination, duration, data)
            return formatted_result

        except json.JSONDecodeError:
            # 如果解析失败，返回原始文本
            return f"⚠️ 数据解析异常，请检查返回格式。\n\n原始结果：\n{result}"

    except Exception as e:
        result = f"[错误] 生成清单时出错：{str(e)}"
        return result

def save_checklist_data(checklist_id, destination, duration, data):
    """保存清单数据到本地JSON文件"""
    import json
    import os
    from datetime import datetime

    # 创建保存目录
    save_dir = "checklist_data"
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    # 准备保存的数据
    save_data = {
        "id": checklist_id,
        "destination": destination,
        "duration": duration,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data": data
    }

    # 保存到文件
    file_path = os.path.join(save_dir, f"{checklist_id}.json")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)

def format_checklist_output(checklist_id, destination, duration, data):
    """格式化清单输出为可读文本（无checkbox）"""

    # 构建HTML输出
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 100%;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
            <h2 style="margin: 0; font-size: 24px;">📋 旅行清单 - {destination} ({duration})</h2>
        </div>

        <div style="background: #e8f5e9; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
            <h3 style="margin: 0 0 10px 0; color: #2e7d32;">📦 行前准备清单</h3>
            <p style="margin: 0; color: #558b2f; font-size: 13px;">💡 提示：此清单仅供参考，请根据实际情况调整</p>
        </div>
    """

    # 生成每个类别的清单
    for category in data.get("checklist", []):
        category_name = category.get("category", "")
        items = category.get("items", [])
        html += f"""
        <div style="margin-bottom: 25px; border: 2px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
            <div style="background: #f5f5f5; padding: 12px 15px; font-weight: bold; font-size: 16px; border-bottom: 1px solid #e0e0e0;">
                🔹 {category_name}
            </div>
            <div style="padding: 15px; background: white;">
        """

        for item in items:
            name = item.get("name", "")
            required = item.get("required", False)
            note = item.get("note", "")
            required_text = "【必带】" if required else "【可选】"

            html += f"""
                <div style="margin-bottom: 12px; padding: 8px; border-radius: 6px; line-height: 1.6;">
                    <span style="color: {'#d32f2f' if required else '#757575'}; font-size: 12px; font-weight: bold;">{required_text}</span>
                    <span style="color: #333; margin-left: 8px; font-weight: {('bold' if required else 'normal')}">{name}</span>
                    {f'<div style="color: #666; font-size: 13px; margin-top: 4px; margin-left: 0;">💡 {note}</div>' if note else ''}
                </div>
            """

        html += """
            </div>
        </div>
        """

    # 预订指引部分（纯文本）
    html += """
        <div style="background: #e3f2fd; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
            <h3 style="margin: 0 0 10px 0; color: #1565c0;">🎫 预订指引</h3>
        </div>
    """

    booking_guides = data.get("booking_guides", {})
    if booking_guides:
        # 交通指引
        if "transport" in booking_guides:
            html += f"""
            <div style="margin-bottom: 20px; padding: 15px; border-left: 4px solid #2196f3; background: #f5f5f5;">
                <h4 style="margin: 0 0 10px 0; color: #1976d2;">✈️ 交通预订</h4>
                <p style="margin: 0; color: #555; line-height: 1.6;">{booking_guides['transport'].get('guide', '')}</p>
            """
            platforms = booking_guides['transport'].get('platforms', [])
            if platforms:
                html += '<p style="margin: 10px 0 5px 0; color: #333; font-weight: bold;">推荐平台：</p><ul style="margin: 0; color: #555;">'
                for platform in platforms:
                    html += f'<li style="margin-bottom: 5px;">{platform}</li>'
                html += '</ul>'
            html += "</div>"

        # 酒店指引
        if "hotel" in booking_guides:
            html += f"""
            <div style="margin-bottom: 20px; padding: 15px; border-left: 4px solid #4caf50; background: #f5f5f5;">
                <h4 style="margin: 0 0 10px 0; color: #388e3c;">🏨 酒店预订</h4>
                <p style="margin: 0; color: #555; line-height: 1.6;">{booking_guides['hotel'].get('guide', '')}</p>
            """
            platforms = booking_guides['hotel'].get('platforms', [])
            if platforms:
                html += '<p style="margin: 10px 0 5px 0; color: #333; font-weight: bold;">推荐平台：</p><ul style="margin: 0; color: #555;">'
                for platform in platforms:
                    html += f'<li style="margin-bottom: 5px;">{platform}</li>'
                html += '</ul>'
            html += "</div>"

        # 景点指引
        if "attractions" in booking_guides:
            html += f"""
            <div style="margin-bottom: 20px; padding: 15px; border-left: 4px solid #ff9800; background: #f5f5f5;">
                <h4 style="margin: 0 0 10px 0; color: #f57c00;">🎯 景点预订</h4>
                <p style="margin: 0; color: #555; line-height: 1.6;">{booking_guides['attractions'].get('guide', '')}</p>
            """
            platforms = booking_guides['attractions'].get('platforms', [])
            if platforms:
                html += '<p style="margin: 10px 0 5px 0; color: #333; font-weight: bold;">推荐平台：</p><ul style="margin: 0; color: #555;">'
                for platform in platforms:
                    html += f'<li style="margin-bottom: 5px;">{platform}</li>'
                html += '</ul>'
            html += "</div>"

    # 温馨提示
    tips = data.get("tips", [])
    if tips:
        html += """
        <div style="background: #fff3e0; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
            <h3 style="margin: 0 0 10px 0; color: #e65100;">💡 温馨提示</h3>
        """
        for tip in tips:
            html += f'<p style="margin: 8px 0; color: #555;">• {tip}</p>'
        html += "</div>"

    # 底部信息
    html += """
        <div style="background: #f5f5f5; padding: 15px; border-radius: 8px; text-align: center; color: #666; font-size: 13px; margin-top: 20px;">
            <p style="margin: 5px 0;">💡 此清单仅供参考，请根据实际情况调整</p>
        </div>
    </div>
    """

    return html


def create_app():
    """创建Gradio应用"""
    # 兴趣偏好选项
    interest_options = [
        "避寒康养", "海岛度假", "文化历史", "温泉养生", "自然风光",
        "美食体验", "摄影采风", "休闲购物", "传统建筑", "民俗体验",
        "慢节奏游", "海滨漫步", "茶文化", "寺庙祈福", "古镇风情",
        "田园风光", "动物观赏", "艺术展览", "传统戏曲", "手工体验",
        "健康养生", "中医理疗", "瑜伽冥想", "森林浴", "阳光浴"
    ]

    # 健康关注点选项
    health_focus_options = [
        "避免过度疲劳", "饮食清淡", "需要靠近医院", "避免高原地区",
        "需要无障碍设施", "避免长时间步行", "注意防晒", "避免潮湿环境",
        "需要安静环境", "控制血压", "控制血糖", "关注空气质量",
        "需要携带药物", "保护心脏", "保持关节灵活", "预防感冒",
        "避免拥挤", "需要良好睡眠", "避免剧烈运动", "注意保暖",
        "多喝水", "定期休息", "避免暴晒", "饮食规律", "适度活动"
    ]

    with gr.Blocks(
        title="🧳 银发族智能旅行助手",
        theme=gr.themes.Soft(primary_hue="purple", secondary_hue="cyan"),
        css="""
        .gr-button {font-size: 18px !important; padding: 12px 20px !important;}
        .gr-textbox input {font-size: 16px !important;}
        .gr-multiselect {min-height: 120px !important;}
        """
    ) as app:
        gr.HTML('''
        <h1 style="text-align:center; font-size:48px; margin-bottom:10px;">
            🧳 银发族智能旅行助手
        </h1>
        <p style="text-align:center; font-size:18px; color:#666; margin-bottom:30px;">
            专为中老年朋友设计的温暖贴心的旅行规划伙伴
        </p>
        ''')

        # 主界面：单Tab设计
        with gr.Row():
            with gr.Column(scale=1):
                gr.HTML('''
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 25px; border-radius: 15px; margin-bottom: 20px; text-align: center;">
                    <h2 style="margin: 0; font-size: 32px;">🌟 目的地推荐</h2>
                    <p style="margin: 10px 0 0 0; font-size: 16px;">根据您的需求智能推荐适合的旅行目的地</p>
                </div>
                ''')

                season = gr.Dropdown(
                    ["春季", "夏季", "秋季", "冬季"],
                    label="🌸 季节",
                    value="秋季",
                    info="选择您计划出行的季节"
                )
                health = gr.Dropdown(
                    ["身体健康", "有慢性病但控制良好", "行动不便但可独立出行"],
                    label="🏥 健康状况",
                    value="身体健康",
                    info="真实反映您的健康状况，便于推荐更合适的目的地"
                )
                budget = gr.Dropdown(
                    ["经济实惠", "舒适型", "豪华型"],
                    label="💰 预算范围",
                    value="舒适型",
                    info="选择您的预算档次"
                )
                interests = gr.CheckboxGroup(
                    choices=interest_options,
                    value=["避寒康养", "温泉养生"],
                    label="🎨 兴趣偏好",
                    info="可选择多个您感兴趣的主题"
                )
                btn1 = gr.Button("🔍 推荐目的地", variant="primary", size="lg")
                output1 = gr.Textbox(
                    label="✨ 推荐结果",
                    lines=15,
                    max_lines=25,
                    info="系统将为您推荐3-5个适合的目的地"
                )

            with gr.Column(scale=1):
                gr.HTML('''
                <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 25px; border-radius: 15px; margin-bottom: 20px; text-align: center;">
                    <h2 style="margin: 0; font-size: 32px;">📋 行程规划</h2>
                    <p style="margin: 10px 0 0 0; font-size: 16px;">为您量身定制舒缓贴心的旅行行程</p>
                </div>
                ''')

                dest = gr.Textbox(
                    label="📍 目的地",
                    info="填写您想去或已选择的目的地"
                )
                dur = gr.Dropdown(
                    ["3-5天", "一周左右", "10-15天", "15天以上"],
                    label="⏰ 旅行时长",
                    value="一周左右"
                )
                mobility = gr.Dropdown(
                    ["行走自如", "需要少量休息", "需要轮椅辅助"],
                    label="🚶 行动能力",
                    value="行走自如"
                )
                health_focus = gr.CheckboxGroup(
                    choices=health_focus_options,
                    value=["避免过度疲劳", "饮食清淡", "定期休息"],
                    label="❤️ 健康关注点",
                    info="可选择多个您的健康关注点"
                )
                btn2 = gr.Button("📋 制定行程", variant="primary", size="lg")
                output2 = gr.Textbox(
                    label="✨ 行程安排",
                    lines=15,
                    max_lines=25,
                    info="为您量身定制的舒缓行程安排"
                )

        # 分割线
        gr.HTML('''
        <div style="margin: 40px 0; border-top: 3px solid #e0e0e0;"></div>
        ''')

        # 旅行清单部分
        with gr.Row():
            with gr.Column():
                gr.HTML('''
                <div style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; padding: 30px; border-radius: 15px; margin-bottom: 20px; text-align: center;">
                    <h2 style="margin: 0; font-size: 32px;">🎁 旅行清单</h2>
                    <p style="margin: 10px 0 0 0; font-size: 16px;">生成专属的行前准备清单，让旅行更轻松</p>
                </div>
                ''')

                gr.HTML('''
                <div style="padding: 20px; background: #e3f2fd; border-radius: 10px; margin-bottom: 20px; border-left: 5px solid #2196f3;">
                    <p style="color: #1565c0; font-size: 15px; margin: 0; line-height: 1.8;">
                        💡 <strong>智能填充：</strong>如果您刚完成行程规划，清单生成时会自动使用您刚才填写的目的地和时长信息！
                    </p>
                </div>
                ''')

                with gr.Row():
                    with gr.Column(scale=1):
                        checklist_origin = gr.Textbox(
                            label="🏠 出发地",
                            value="",
                            info="填写您的出发城市（例如：北京、上海、广州等）"
                        )
                        checklist_dest = gr.Textbox(
                            label="📍 目的地",
                            value="",
                            placeholder="（例如：北京、普陀山、杭州等）",
                            info="填写目的地"
                        )

                    with gr.Column(scale=1):
                        checklist_dur = gr.Dropdown(
                            ["3-5天", "一周左右", "10-15天", "15天以上"],
                            label="⏰ 旅行时长",
                            value="一周左右",
                            info="选择旅行时长"
                        )
                        checklist_needs = gr.Textbox(
                            label="⚕️ 特殊需求",
                            value="身体健康，常规旅行",
                            info="例如：高血压、糖尿病、需携带医疗器械等"
                        )

                # Loading输出
                output3_loading = gr.HTML(value="")
                btn3 = gr.Button("🎯 生成专属清单", variant="primary", size="lg")
                output3 = gr.HTML(
                    label="✨ 清单内容",
                    value="""
                    <div style="padding: 60px 40px; background: linear-gradient(135deg, #e3f2fd 0%, #f3e5f5 100%); border-radius: 15px; text-align: center; border: 2px dashed #9c27b0;">
                        <div style="font-size: 64px; margin-bottom: 20px;">📋</div>
                        <h3 style="color: #6a1b9a; margin: 0 0 15px 0; font-size: 24px;">旅行清单尚未生成</h3>
                        <p style="color: #7b1fa2; margin: 0; font-size: 16px; line-height: 1.8;">
                            填写好目的地、旅行时长和特殊需求后，点击"生成专属清单"按钮<br/>
                            AI将为您生成详细的行前准备清单
                        </p>
                    </div>
                    """
                )

        # 事件绑定
        def show_loading():
            return """
            <script>
                (function() {
                    // 移除可能存在的旧遮罩
                    const oldOverlay = document.getElementById('app_loading_overlay');
                    if (oldOverlay) {
                        oldOverlay.remove();
                    }

                    // 创建新的全屏遮罩，直接插入到body
                    const overlay = document.createElement('div');
                    overlay.id = 'app_loading_overlay';
                    overlay.innerHTML = `
                        <div style="
                            position: fixed !important;
                            top: 0 !important;
                            left: 0 !important;
                            width: 100vw !important;
                            height: 100vh !important;
                            min-height: 100vh !important;
                            background-color: rgba(0,0,0,0.85) !important;
                            z-index: 2147483647 !important;
                            display: flex !important;
                            align-items: center !important;
                            justify-content: center !important;
                            animation: fadeIn 0.3s ease-in;
                            pointer-events: all !important;
                        ">
                            <div style="
                                background: white;
                                padding: 80px 100px !important;
                                border-radius: 25px;
                                text-align: center;
                                box-shadow: 0 15px 60px rgba(0,0,0,0.7);
                                animation: pulse 2s ease-in-out infinite;
                                max-width: 700px !important;
                                margin: 40px;
                            ">
                                <div style="
                                    width: 120px !important;
                                    height: 120px !important;
                                    margin: 0 auto 40px;
                                    border: 10px solid #f0f0f0;
                                    border-top: 10px solid #667eea;
                                    border-radius: 50%;
                                    animation: spin 1s linear infinite;
                                "></div>
                                <h2 style="
                                    font-size: 36px !important;
                                    color: #333;
                                    margin: 0 0 20px 0;
                                    font-weight: bold;
                                ">正在生成专属清单</h2>
                                <p style="
                                    font-size: 22px !important;
                                    color: #666;
                                    margin: 0;
                                    line-height: 1.6;
                                ">AI正在为您精心准备，请稍候...</p>
                            </div>
                            <style>
                                @keyframes spin {
                                    0% { transform: rotate(0deg); }
                                    100% { transform: rotate(360deg); }
                                }
                                @keyframes pulse {
                                    0%, 100% { transform: scale(1); }
                                    50% { transform: scale(1.05); }
                                }
                                @keyframes fadeIn {
                                    from { opacity: 0; }
                                    to { opacity: 1; }
                                }
                                #app_loading_overlay {
                                    position: fixed !important;
                                    top: 0 !important;
                                    left: 0 !important;
                                    width: 100vw !important;
                                    height: 100vh !important;
                                    z-index: 2147483647 !important;
                                }
                            </style>
                        </div>
                    `;
                    document.body.appendChild(overlay);
                })();
            </script>
            """

        def hide_loading():
            return """
            <script>
                (function() {
                    const overlay = document.getElementById('app_loading_overlay');
                    if (overlay) {
                        overlay.remove();
                    }
                })();
            </script>
            """

        # 按钮点击事件
        btn1.click(
            fn=generate_destination_recommendation,
            inputs=[season, health, budget, interests],
            outputs=[output1]
        )

        btn2.click(
            fn=generate_itinerary_plan,
            inputs=[dest, dur, mobility, health_focus],
            outputs=[output2]
        )

        # 行程规划的信息自动填充到旅行清单
        dest.change(
            fn=lambda x: x,
            inputs=[dest],
            outputs=[checklist_dest]
        )

        dur.change(
            fn=lambda x: x,
            inputs=[dur],
            outputs=[checklist_dur]
        )

        # 清单生成（带Loading效果）
        btn3.click(
            fn=show_loading,
            outputs=[output3_loading]
        ).then(
            fn=generate_checklist,
            inputs=[checklist_dest, checklist_dur, checklist_needs, output2],
            outputs=[output3]
        ).then(
            fn=hide_loading,
            outputs=[output3_loading]
        )

        # 添加底部说明
        gr.HTML('''
        <div style="text-align:center; margin-top:30px; padding:20px; background:#f5f5f5; border-radius:10px;">
            <p style="color:#666; font-size:14px;">
                💡 温馨提示：此应用为AI生成内容，仅供参考。具体行程请结合自身实际情况调整。<br/>
                🏥 建议出行前咨询医生，携带必要药品，关注目的地医疗资源。
            </p>
        </div>
        ''')

    return app

if __name__ == "__main__":
    print("正在启动银发族智能旅行助手...")
    print("请在浏览器中访问: http://localhost:7860")
    print("按 Ctrl+C 停止服务")
    app = create_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        inbrowser=True,
        share=False,
        show_error=True
    )
