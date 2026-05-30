"""文案模块 — LLM个性化邀约文案生成 & 自动发送

核心组件:
- invitation: InvitationWriter (LLM 文案生成)
- sender: InvitationSender (Playwright 自动发送)

使用大语言模型:
- 根据候选人信息生成个性化邀约文案
- 支持多种语气风格
- 人工预览确认后发送 (G-09)
"""
