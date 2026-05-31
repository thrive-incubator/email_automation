export type ActionType =
  | "reply"
  | "flag"
  | "discard"
  | "label"
  | "crm_handoff"
  | "exclude";
export type SendMode = "draft" | "send";

export interface Decision {
  id: string;
  email_id: string;
  thread_id: string;
  sender: string;
  sender_email: string;
  subject: string;
  snippet: string;
  body: string;
  received_at: string;
  matched_rule_id: string | null;
  matched_rule_name: string | null;
  confidence: number;
  safety_flag: boolean;
  sales_opportunity: boolean;
  reasoning: string;
  action_type: ActionType;
  send_mode: SendMode;
  summary: string;
  proposed_draft: string;
  voice_used: string | null;
  knowledge_refs: string[];
  label: string | null;
  handoff_payload: Record<string, unknown> | null;
  status: string;
  user_edited_draft: string | null;
  execution_result: string | null;
  created_at: string;
}

export interface InboxItem {
  id: string;
  thread_id: string;
  sender: string;
  sender_email: string;
  subject: string;
  snippet: string;
  body: string;
  received_at: string;
  processed: boolean;
  decision_id: string | null;
}

export interface RunResponse {
  fetched: number;
  new: number;
  skipped: number;
  decisions: Decision[];
}

export interface Rule {
  id: string;
  name: string;
  description: string;
  filter_prompt: string;
  action_type: ActionType;
  voice_file: string | null;
  knowledge_files: string[];
  reply_prompt: string | null;
  confidence_threshold: number;
  send_mode: SendMode;
  label: string | null;
  enabled: boolean;
  priority: number;
}

export type RuleCreate = Omit<Rule, "id">;

export interface BrainIndex {
  voices: string[];
  knowledge: string[];
  guardrails: string[];
}

export interface BrainFile {
  kind: "voice" | "knowledge" | "guardrails";
  name: string;
  content: string;
}

export interface SubmitItem {
  decision_id: string;
  edited_draft?: string | null;
  save_to_knowledge?: string | null;
}

export interface SubmitResult {
  decision_id: string;
  ok: boolean;
  message: string;
}

export interface SettingsView {
  email_provider: string;
  gemini_model: string;
  anthropic_model: string;
  gmail_connected: boolean;
  crm_handoff_target: string;
}

export interface ProviderStatus {
  name: string;
  configured: boolean;
  ok: boolean;
  detail: string;
}
