import { AgentPlan, AgentMessage, nextMessageId } from "../../shared/types";
import { fromDbRole } from "./sentry-api";
import type { ChatMessageOut } from "./sentry-api";

export function convertDbMessages(rawMessages: ChatMessageOut[]): AgentMessage[] {
  return rawMessages.map((m) => ({
    id: nextMessageId(),
    role: m.metadata?.activity ? "activity" as const
        : m.metadata?.thinking ? "thinking" as const
        : m.metadata?.vbaCode ? "vba_code" as const
        : fromDbRole(m.role),
    content: m.content,
    timestamp: m.created_at ? new Date(m.created_at).getTime() : Date.now(),
    ...(m.metadata?.plan ? { plan: m.metadata.plan as unknown as AgentPlan, planStatus: (m.metadata.planStatus as AgentMessage["planStatus"]) || "built" } : {}),
    ...(m.metadata?.vbaCode ? { vbaCode: m.metadata.vbaCode as AgentMessage["vbaCode"] } : {}),
    ...(m.metadata?.activity ? { activity: m.metadata.activity as AgentMessage["activity"] } : {}),
    ...(m.metadata?.thinking ? { thinkingSections: m.metadata.thinking as AgentMessage["thinkingSections"] } : {}),
    ...(m.metadata?.thinkingDurationSecs !== undefined ? { thinkingDurationSecs: m.metadata.thinkingDurationSecs as number } : {}),
    ...(m.metadata?.checkpointId ? { checkpointId: m.metadata.checkpointId as string } : {}),
  }));
}
