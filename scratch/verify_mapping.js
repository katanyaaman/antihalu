const fs = require('fs');
const path = require('path');

const available = fs.readdirSync(path.join(__dirname, '..', 'assets', 'providers'));
console.log('Available count:', available.length);

const mapping = {
  // OAuth
  'claude_code': 'claude.png',
  'antigravity': 'antigravity.png',
  'openai_codex': 'codex.png',
  'qoder': 'qoder.png',
  'qoder_cn': 'qoder-cn.png',
  'github_copilot': 'copilot.png',
  'cursor_ide': 'cursor.png',
  'kilo_code': 'kilocode.png',
  'cline': 'cline.png',
  'minimax_code': 'minimax.png',
  'minimax_global': 'minimax-cn.png',
  'cline_pass': 'clinepass.png',
  'code_buddy': 'codebuddy-intl.png',
  'code_buddy_cn': 'codebuddy-cn.png',
  'muse_meta': 'muse.png',
  'zai_glm': 'glm.png',
  'kimi': 'kimi.png',
  'grok_cli': 'grok-cli.png',
  'xai_grok': 'xai.png',
  'xiaomi_mimo': 'xiaomi-mimo.png',
  'zed': 'zed.png',

  // Free Tier
  'opencode_free': 'opencode.png',
  'gemini_cli': 'gemini-cli.png',
  'kiro_ai': 'kiro.png',
  'openrouter_free': 'openrouter.png',
  'nvidia_nim': 'nvidia.png',
  'ollama_cloud': 'ollama.png',
  'vertex_ai': 'vertex.png',
  'gemini_free': 'gemini.png',
  'cloudflare': 'cloudflare-ai.png',
  'poolside': 'poolside.png',
  'byteplus_modelark': 'byteplus.png',
  'kimchi': 'kimchi.png',
  'agnes_ai': 'agnes.png',
  'api_airforce': 'api-airforce.png',
  'bazaarlink': 'bazaarlink.png',
  'kilo_gateway': 'kilo-gateway.png',

  // API Key Providers
  'cerebras': 'cerebras.png',
  'xiaomi_mimo_token': 'xiaomi-tokenplan.png',
  'alibaba': 'alicode.png',
  'alibaba_coding': 'alicode-intl.png',
  'alibaba_studio': 'alims-intl.png',
  'alibaba_token_plan': 'alitp-intl.png',
  'anthropic': 'anthropic.png',
  'atria_dawn': 'atria.png',
  'aws_bedrock': 'bedrock.png',
  'aws_bedrock_xai': 'bedrock-xai.png',
  'azure_openai': 'azure.png',
  'b_ai': 'bai.png',
  'baidu_qianfan': 'baidu.png',
  'blackbox_ai': 'blackbox.png',
  'chutes_ai': 'chutes.png',
  'cohere': 'cohere.png',
  'command_code': 'commandcode.png',
  'dahl_inference': 'dahl.png',
  'deepseek': 'deepseek.png',
  'featherless': 'featherless.png',
  'fireworks_ai': 'fireworks.png',
  'glm_china': 'glm-cn.png',
  'groq': 'groq.png',
  'hyperbolic': 'hyperbolic.png',
  'llm7': 'llm7.png',
  'minimax_china': 'minimax-cn.png',
  'minimax_coding': 'minimax.png',
  'mistral': 'mistral.png',
  'morph': 'morph.png',
  'nebius_ai': 'nebius.png',
  'ollama_local': 'ollama-local.png',
  'openai': 'openai.png',
  'opencode_go': 'opencode-go.png',
  'opencode_zen': 'opendesign.png',
  'perplexity': 'perplexity.png',
  'perplexity_agent': 'perplexity-agent.png',
  'siliconflow': 'siliconflow.png',
  'tencent_hunyuan': 'tencent.png',
  'together_ai': 'together.png',
  'token_harbor': 'tokenharbor.png',
  'token_router': 'tokenrouter.png',
  'venice_ai': 'venice.png',
  'vercel_ai_gateway': 'vercel-ai-gateway.png',
  'vertex_partner': 'vertex-partner.png',
  'volcengine_ark': 'volcengine-ark.png'
};

const missing = [];
for (const [id, f] of Object.entries(mapping)) {
  if (!available.includes(f)) {
    missing.push({ id, f });
  }
}
console.log('Missing count:', missing.length, missing);
