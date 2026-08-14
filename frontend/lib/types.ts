export type Source = {
  doc_id: string;
  title: string;
  text: string;
  score: number;
};

export type RAGResponse = {
  answer: string;
  sources: Source[];
  error?: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  created_at: string;
};
