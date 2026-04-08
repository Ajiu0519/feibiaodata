"""
AI 每日总结功能
使用 MiniMax API 生成数据总结
"""
import requests
from datetime import datetime

MINIMAX_API_KEY = "sk-cp-bVupXbe8ZgkjOXcdYc3C_fpRzUWOFO8MTwJLnSAy4vM4hL9chtNYPax3EmOgfrjcuBnkeO8lTlfje-gqjO3tGhXWdognuROJ6bRkiudaxfqG1XrQTba-rG0"
MINIMAX_API_URL = "https://api.minimax.chat/v1/text/chatcompletion_v2"
MODEL_NAME = "MiniMax-M2.7"

def generate_summary(daily_data, camp_data, date_str=None):
    """生成每日数据总结"""
    
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
    
    # 计算汇总数据
    total_pay = sum(item.get('支付成功例子数', 0) or 0 for item in daily_data)
    total_effective = sum(item.get('有效例子数', 0) or 0 for item in daily_data)
    total_addwx = sum(item.get('加微例子数', 0) or 0 for item in daily_data)
    
    # 按渠道汇总
    channel_summary = {}
    for item in daily_data:
        ch = item.get('渠道', '未知')
        if ch not in channel_summary:
            channel_summary[ch] = {'pay': 0, 'effective': 0, 'addwx': 0}
        channel_summary[ch]['pay'] += item.get('支付成功例子数', 0) or 0
        channel_summary[ch]['effective'] += item.get('有效例子数', 0) or 0
        channel_summary[ch]['addwx'] += item.get('加微例子数', 0) or 0
    
    # 找出跑得最好的和最差的渠道
    if channel_summary:
        sorted_channels = sorted(channel_summary.items(), key=lambda x: x[1]['pay'], reverse=True)
        best_channel = sorted_channels[0]
        worst_channel = sorted_channels[-1] if len(sorted_channels) > 1 else best_channel
    else:
        best_channel = worst_channel = ('无数据', {'pay': 0})
    
    # 构建 prompt
    prompt = f"""你是数据分析师。请根据以下数据，为 {date_str} 的运营情况生成一份简洁的每日总结：

【核心数据】
- 总支付成功数: {total_pay}
- 总有效例子数: {total_effective}
- 总加微例子数: {total_addwx}
- 活跃渠道数: {len(channel_summary)}

【各渠道数据】
"""
    for ch, data in channel_summary.items():
        prompt += f"- {ch}: 支付{data['pay']}, 有效{data['effective']}, 加微{data['addwx']}\n"
    
    prompt += f"""
【亮点】
- 最佳渠道: {best_channel[0]} (支付{best_channel[1]['pay']})
"""
    if len(sorted_channels) > 1:
        prompt += f"- 待优化渠道: {worst_channel[0]} (支付{worst_channel[1]['pay']})\n"
    
    prompt += """
【要求】
1. 总结当日整体运营情况（2-3句话）
2. 指出需要关注的渠道或H5ID（如果有）
3. 给出简单的优化建议（1-2条）
4. 用中文回复，语气专业但易懂
"""

    try:
        response = requests.post(
            MINIMAX_API_URL,
            headers={
                "Authorization": f"Bearer {MINIMAX_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MODEL_NAME,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 500
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            # MiniMax 返回格式
            if result.get('choices') and len(result['choices']) > 0:
                summary = result['choices'][0]['message'].get('content', '')
                if summary:
                    return {
                        "date": date_str,
                        "summary": summary,
                        "stats": {
                            "total_pay": total_pay,
                            "total_effective": total_effective,
                            "total_addwx": total_addwx,
                            "channel_count": len(channel_summary),
                            "best_channel": {"name": best_channel[0], "pay": best_channel[1]['pay']},
                            "worst_channel": {"name": worst_channel[0], "pay": worst_channel[1]['pay']}
                        },
                        "status": "success"
                    }
            
            # 如果内容为空，返回默认消息
            return {
                "date": date_str,
                "summary": f"AI总结生成中（模型响应为空，请稍后重试）",
                "stats": {
                    "total_pay": total_pay,
                    "total_effective": total_effective,
                    "total_addwx": total_addwx,
                    "channel_count": len(channel_summary),
                    "best_channel": {"name": best_channel[0], "pay": best_channel[1]['pay']},
                    "worst_channel": {"name": worst_channel[0], "pay": worst_channel[1]['pay']}
                },
                "status": "partial"
            }
        else:
            return {
                "date": date_str,
                "summary": f"AI总结生成失败: {response.status_code}",
                "error": response.text,
                "status": "error"
            }
    except Exception as e:
        return {
            "date": date_str,
            "summary": f"AI总结生成异常: {str(e)}",
            "status": "error"
        }
