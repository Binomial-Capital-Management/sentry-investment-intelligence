import type { ModelInfo, ModelId } from '@/types';

// Import logos from assets
import gptLogo from '@/assets/model-logos/gpt-logo.png';
import claudeLogo from '@/assets/model-logos/claude-logo.svg.png';
import geminiLogo from '@/assets/model-logos/gemini-logo.png';
import grokLogo from '@/assets/model-logos/grok.png';
import kimiLogo from '@/assets/model-logos/Kimi-logo-2025.png';
import qwenLogo from '@/assets/model-logos/Qwen_logo.svg.png';
import glmLogo from '@/assets/model-logos/Z.ai_(company_logo).svg.png';

export const MODELS: Record<ModelId, ModelInfo> = {
  'gpt-6-astra': {
    id: 'gpt-6-astra',
    name: 'GPT-6 Astra',
    provider: 'OpenAI',
    logo: gptLogo,
    available: true,
    category: 'powerful',
    description: 'OpenAI\'s most capable model for the most demanding work',
    contextLimit: '1M tokens',
  },
  'gpt-6.1-sol': {
    id: 'gpt-6.1-sol',
    name: 'GPT-6.1 Sol',
    provider: 'OpenAI',
    logo: gptLogo,
    available: true,
    category: 'versatile',
    description: 'Near-Astra performance for complex work at a lower cost',
    contextLimit: '1M tokens',
  },
  'gpt-6-luna': {
    id: 'gpt-6-luna',
    name: 'GPT-6 Luna',
    provider: 'OpenAI',
    logo: gptLogo,
    available: true,
    category: 'fast',
    description: 'Most efficient GPT-6 model for focused, high-volume tasks',
    contextLimit: '1M tokens',
  },
  'litellm/anthropic/claude-fable-5-1': {
    id: 'litellm/anthropic/claude-fable-5-1',
    name: 'Claude Fable 5.1',
    provider: 'Anthropic',
    logo: claudeLogo,
    available: true,
    category: 'powerful',
    description: 'Anthropic\'s most capable model for demanding reasoning and long-horizon work',
    contextLimit: '1M tokens',
  },
  'litellm/anthropic/claude-opus-5-5': {
    id: 'litellm/anthropic/claude-opus-5-5',
    name: 'Claude Opus 5.5',
    provider: 'Anthropic',
    logo: claudeLogo,
    available: true,
    category: 'powerful',
    description: 'Frontier reasoning for complex analysis and agentic workflows',
    contextLimit: '1M tokens',
  },
  'litellm/anthropic/claude-sonnet-5-5': {
    id: 'litellm/anthropic/claude-sonnet-5-5',
    name: 'Claude Sonnet 5.5',
    provider: 'Anthropic',
    logo: claudeLogo,
    available: true,
    category: 'versatile',
    description: 'Speed and capability for everyday analysis and multi-step workflows',
    contextLimit: '1M tokens',
  },
  'litellm/anthropic/claude-haiku-4-5-20251001': {
    id: 'litellm/anthropic/claude-haiku-4-5-20251001',
    name: 'Claude Haiku 4.5',
    provider: 'Anthropic',
    logo: claudeLogo,
    available: true,
    category: 'fast',
    description: 'Quick responses with good accuracy',
    contextLimit: '200K tokens',
  },
  'litellm/gemini/gemini-4-argon': {
    id: 'litellm/gemini/gemini-4-argon',
    name: 'Gemini 4 Argon',
    provider: 'Google',
    logo: geminiLogo,
    available: true,
    category: 'powerful',
    description: 'Google\'s flagship reasoning model with multimodal support',
    contextLimit: '1M tokens',
  },
  'litellm/gemini/gemini-3.8-flash': {
    id: 'litellm/gemini/gemini-3.8-flash',
    name: 'Gemini 3.8 Flash',
    provider: 'Google',
    logo: geminiLogo,
    available: true,
    category: 'versatile',
    description: 'Latest Gemini Flash tuned for tool use and streaming',
    contextLimit: '1M tokens',
  },
  'litellm/gemini/gemini-3.5-flash-lite': {
    id: 'litellm/gemini/gemini-3.5-flash-lite',
    name: 'Gemini 3.5 Flash Lite',
    provider: 'Google',
    logo: geminiLogo,
    available: true,
    category: 'fast',
    description: 'Lowest-latency Gemini model for quick responses',
  },
  'litellm/xai/grok-4.7': {
    id: 'litellm/xai/grok-4.7',
    name: 'Grok 4.7',
    provider: 'xAI',
    logo: grokLogo,
    available: true,
    category: 'powerful',
    description: 'xAI\'s most capable Grok model for deep reasoning and analysis',
    contextLimit: '500K tokens',
  },
  'litellm/xai/grok-4.20-0309-non-reasoning': {
    id: 'litellm/xai/grok-4.20-0309-non-reasoning',
    name: 'Grok 4.20 Fast',
    provider: 'xAI',
    logo: grokLogo,
    available: true,
    category: 'fast',
    description: 'High-speed Grok responses without reasoning traces',
    contextLimit: '1M tokens',
  },
  'litellm/moonshot/kimi-k3': {
    id: 'litellm/moonshot/kimi-k3',
    name: 'Kimi K3',
    provider: 'Moonshot',
    logo: kimiLogo,
    available: true,
    category: 'powerful',
    description: 'Agentic reasoning and tool use with a 1M-token context',
    contextLimit: '1M tokens',
  },
  'litellm/dashscope/qwen3.8-max': {
    id: 'litellm/dashscope/qwen3.8-max',
    name: 'Qwen 3.8 Max',
    provider: 'Alibaba',
    logo: qwenLogo,
    available: true,
    category: 'powerful',
    description: 'Alibaba\'s flagship Qwen model for agentic reasoning and tool use',
  },
  'litellm/zai/glm-5.3': {
    id: 'litellm/zai/glm-5.3',
    name: 'GLM-5.3',
    provider: 'Zhipu',
    logo: glmLogo,
    available: true,
    category: 'powerful',
    description: 'Agentic model with interleaved thinking and tool calling',
  },
};

export const getModelById = (id: ModelId): ModelInfo => {
  // Return the model or fall back to the default if not found
  return MODELS[id] || MODELS['gpt-6.1-sol'];
};

export const getAvailableModels = (): ModelInfo[] => {
  return Object.values(MODELS).filter(model => model.available);
};

export const getModelsByCategory = (category: 'fast' | 'versatile' | 'powerful'): ModelInfo[] => {
  return Object.values(MODELS).filter(model => model.category === category);
};
