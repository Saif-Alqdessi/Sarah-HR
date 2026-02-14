export type InterviewStatus = "pending" | "in_progress" | "completed" | "failed";

export interface Interview {
  id: string;
  candidateId: string;
  vapiSessionId?: string;
  status: InterviewStatus;
  startedAt?: string;
  completedAt?: string;
  durationSeconds?: number;
  audioUrl?: string;
  fullTranscript?: unknown;
  questionsAsked?: unknown;
  createdAt: string;
  updatedAt: string;
}
