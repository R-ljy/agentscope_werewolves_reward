# -*- coding: utf-8 -*-
"""
Review prompt generator for the Werewolves multi-agent game.

This prompt is is used AFTER each game ends.
Each agent will receive its role, final reward, action trace, and the game outcome.
"""

# --- GLOBAL CONSTANT: THE STRUCTURED PROMPT TEMPLATE ---
# Use .format() to insert variables into this template
REVIEW_PROMPT_TEMPLATE = """
你现在需要对这一局狼人杀游戏进行结构化复盘与自我总结。

你的身份（role）：**{role}**
本局游戏结果是：**{game_outcome}**
你的最终平均 Reward：**{avg_reward:.3f}**
你的关键行为记录如下（系统自动整理的行动轨迹）： **{action_trace}**
{teammates_note}

请严格按照下面 8 个部分输出复盘内容：

----------------------------------------
### 1. 【角色目标与结果判断】
重述你作为 **{role}** 的主要胜利目标。
请判断：你是否围绕该目标行动？你本局是否坚持了阵营策略？
请明确说明：**{game_outcome}** 这一结果是否意味着你的阵营目标已达成？

----------------------------------------
### 2. 【关键行动总结】
列出你本局的 **3~5 个关键行动**（包括夜晚行动、白天发言、投票、策略选择等）。
解释这些行动背后的意图，并说明它们是属于**战略性**（长期目标）还是**战术性**（短期应对）。

----------------------------------------
### 3. 【成功策略分析】
分析你本局中哪些行动是成功且有价值的。
这些动作如何帮助你的阵营获胜（或减少损失）？请具体分析其中**最出乎对手预料**的一个行动。

----------------------------------------
### 4. 【失败策略分析】
列出你最值得反思的 **2~3 个错误或不佳行动**。
请分析这些错误是否导致了队友的**过早出局**或你自己的**身份暴露**？如果重来一次，你会如何修正？

----------------------------------------
### 5. 【信息管理（Information Strategy）】
分析你本局对身份推理、情报判断的质量：
- 你是否被关键信息误导？
- 请分析你**最错误的/最正确的**一个身份判断，并解释支撑这个判断的关键信息是什么。
- 你是否主动且成功地**误导**了其他玩家？

----------------------------------------
### 6. 【协作与对抗策略】
结合你的阵营，具体分析：
- 你是否有效地与队友合作？是否有协作失误？
{teammates_analysis_prompt}
- 你对白方/黑方阵营的压制/反击是否有效？

----------------------------------------
### 7. 【Reward 自我解释】
结合 reward 规则，明确说明：
- 哪些行为为你带来了正 reward？为什么？
- 哪些行为为你带来了负 reward？为什么？
- 你认为当前 Reward 机制是否**公平地评估**了你的表现？有何不足？

----------------------------------------
### 8. 【下一局可执行的改进方案】
给出 **2~3 条明确、具体、可执行的行动策略**，用于下一局提升表现。
这些策略必须是可操作的（例如：“在D1发言时，无论身份如何，优先对发言靠后的玩家施加压力”），而不是抽象的建议。

----------------------------------------

请用结构化 Markdown 形式输出，不要遗漏任何部分。
"""


def generate_review_prompt(
    role: str,
    avg_reward: float,
    action_trace: str,
    game_outcome: str,  # e.g., "胜利" (Win) or "失败" (Loss)
    teammates_exposed: list[str] = None  # List of known exposed teammate roles
) -> str:
    """
    Generate a structured review prompt for a single agent.

    Args:
        role (str): role of the agent (werewolf/villager/seer/witch/hunter)
        avg_reward (float): final average reward for the agent
        action_trace (str): the key action logs of this agent
        game_outcome (str): The final result of the game ("胜利" or "失败")
        teammates_exposed (list[str], optional): List of known exposed teammate roles.

    Returns:
        str: A fully structured, high-quality reflection prompt.
    """

    # 1. Handle teammates information (dynamic section)
    teammates_analysis_prompt = ""
    teammates_note = ""

    if teammates_exposed and role in ["Werewolf", "Wolf", "狼人"]:
        # Specific prompt addition for wolves reflecting on team
        teammates_list_str = "、".join(teammates_exposed)
        teammates_analysis_prompt = (
            f"- 请说明你对已暴露的队友（{teammates_list_str}）的行动支持/掩护策略是否成功，有哪些失误？"
        )
        teammates_note = (
            f"你的部分队友身份（最终暴露）：**{teammates_list_str}**"
        )
    
    # 2. Format the template
    return REVIEW_PROMPT_TEMPLATE.format(
        role=role,
        avg_reward=avg_reward,
        action_trace=action_trace,
        game_outcome=game_outcome,
        teammates_analysis_prompt=teammates_analysis_prompt,
        teammates_note=teammates_note
    )
